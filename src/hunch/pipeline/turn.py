"""The turn pipeline (design.md, "Mimari genel bakış"; Phase 3).

Reply path, in this order (invariant 4: the value gate is always last):
  1. "is the input English?" check -> one-turn instruction if not
  2. working memory: last N exchanges verbatim + rolling session summary
  3. cue extraction (LLM + rule-based dates); the query embedding runs on CPU in parallel
  4. activation over the candidates: upper memories enter reasoning, lower ones only act below;
     every recall is reconsolidated
  5. drive vector from the lower traces; hunch triggers (Phase 4): if the user asks why about a
     hunch-chosen reply, or accepts the offer to think about it, a reflection attempt runs and a
     one-turn instruction carries the hunch in words plus what was unlocked, nothing more
  6. reasoning prompt -> all candidates in one batched call
  7. candidate filter (all fail -> fixed fallback reply)
  8. judge: quality and core values for the remaining candidates, one greedy call
  9. modulation: selection above the quality floor, small exploration
 10. value gate on the chosen candidate (rule checks + judge verdict), then the next ones
 11. reply; a Hunch is stored if the drive's pick materially changed the choice; raw turns
     appended, turn log written
After the reply (off the latency path): the user's message is encoded as a memory, what a
reflection unlocked is stored as a realisation memory, a strong conflict triggers a reflection of
its own, and turns that left the working memory are folded into the session summary.

Every model prompt is built by hunch.pipeline.prompt, hunch.values.gate or
hunch.recall.cues; none of them receives lower traces, drive values or log content (invariant 2,
tests/test_pipeline_prompts.py).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from hunch.config import Config
from hunch.drive.drive import (
    LowerTrace,
    candidate_features,
    compute_drive,
    drive_score,
    summarize_traces,
    trace_weight,
)
from hunch.drive.modulation import Scored, Selection, select
from hunch.llm.types import ChatLLM, SamplingSettings
from hunch.memory.embeddings import Embedder
from hunch.memory.encoding import encode_memory
from hunch.memory.schema import Episode
from hunch.memory.store import MemoryStore, select_working_memory
from hunch.observability.turn_log import ReflectionLog, TurnLog
from hunch.pipeline.checks import admits_no_memory, asks_about_past, is_english_input
from hunch.pipeline.filter import (
    HunchTurn,
    check_candidate,
    content_words,
    filter_candidates,
    trim_to_last_sentence,
)
from hunch.pipeline.prompt import (
    NOT_ENGLISH_INSTRUCTION,
    RECALL_COVERS_INSTRUCTION,
    RecalledLine,
    age_label,
    build_reasoning_messages,
    build_summary_messages,
    hunch_feeling,
    think_more_instruction,
    why_instruction,
)
from hunch.recall.activation import SECONDS_PER_DAY
from hunch.recall.cues import CueExtraction, extract_cues
from hunch.recall.involuntary import SessionRecallState
from hunch.recall.retrieve import recall, reconsolidate
from hunch.reflection.records import MAX_LEVEL, Hunch, SourceRef
from hunch.reflection.reflect import ReflectionOutcome, Reflector
from hunch.reflection.triggers import accepts_offer, asks_why
from hunch.values.core import CoreValues
from hunch.values.gate import (
    Verdict,
    build_judge_messages,
    build_second_opinion_messages,
    disclosure_hits,
    disclosure_terms,
    judge_context,
    parse_second_opinion,
    parse_verdicts,
)

CANDIDATE_IDS = "abcdefghij"
JUDGE_CONTEXT_EXCHANGES = 3  # the judge sees the last few exchanges, not the whole window
CUE_MAX_NEW_TOKENS = 256
SUMMARY_MAX_NEW_TOKENS = 256


@dataclass
class Session:
    """One conversation with one user; lives as long as the chat (not persisted)."""

    conversation_id: str
    user: str
    recall_state: SessionRecallState = field(default_factory=SessionRecallState)
    summary: str = ""
    summarized_upto: int = -1  # highest turn_index already folded into the summary
    turn_no: int = 0
    last_hunch_id: str | None = None  # the hunch that chose the previous reply, if any
    offered_hunch_id: str | None = None  # "want me to think about it?" is open for this hunch


@dataclass(frozen=True)
class TurnResult:
    reply: str
    turn_id: str
    log: dict[str, Any]  # the design.md turn log record
    details: dict[str, Any]  # admin details: texts, reasons, latency
    cues: CueExtraction
    user_episode: Episode
    query_vec: np.ndarray | None
    hunch: Hunch | None = None  # created this turn
    reflection: ReflectionOutcome | None = None  # triggered by this message (ask / think_more)
    conflict: bool = False  # the hunch's pick is far below the best quality: reflect after reply


class _Timer:
    def __init__(self) -> None:
        self.stages: dict[str, float] = {}
        self._t = time.perf_counter()

    def lap(self, name: str) -> None:
        now = time.perf_counter()
        self.stages[name] = round(now - self._t, 3)
        self._t = now


class TurnPipeline:
    def __init__(
        self,
        cfg: Config,
        values: CoreValues,
        llm: ChatLLM,
        store: MemoryStore,
        embedder: Embedder | None,
        turn_log: TurnLog | None = None,
        clock: Callable[[], float] = time.time,
        seed: int = 0,
        new_id: Callable[[], str] = lambda: uuid.uuid4().hex,
        reflection_log: ReflectionLog | None = None,
    ) -> None:
        self.cfg = cfg
        self.values = values
        self.llm = llm
        self.store = store
        self.embedder = embedder
        self.turn_log = turn_log
        self.clock = clock
        self.rng = np.random.default_rng(seed)
        self.new_id = new_id
        if reflection_log is None and turn_log is not None:
            reflection_log = ReflectionLog(turn_log.dir, core_dir=Path(turn_log.core_dir))
        # Reflection draws come from their own seeded stream, so they don't shift the turn's.
        self.reflector = Reflector(
            cfg.reflection, store, np.random.default_rng([seed, 4]), self._feeling,
            cfg.encoding, reflection_log, new_id, clock,
        )  # fmt: skip
        self._pool = ThreadPoolExecutor(max_workers=1)
        gen = cfg.generation
        self.candidate_sampling = SamplingSettings(
            max_new_tokens=gen.max_new_tokens,
            temperature=gen.temperature,
            top_p=gen.top_p,
            top_k=gen.top_k,
        )

    # --- helpers ---------------------------------------------------------------------------------

    def new_session(self, user: str, conversation_id: str | None = None) -> Session:
        return Session(conversation_id or f"c-{self.new_id()[:8]}", user)

    def _greedy(self, max_new_tokens: int) -> SamplingSettings:
        return SamplingSettings(max_new_tokens=max_new_tokens, do_sample=False)

    def _seed(self) -> int:
        return int(self.rng.integers(0, 2**31 - 1))

    def _window(self, turns: list[Episode]):
        wm = self.cfg.working_memory
        return select_working_memory(turns, wm.max_turns, wm.max_tokens, self.llm.count_tokens)

    # --- reply path ------------------------------------------------------------------------------

    def turn(
        self,
        session: Session,
        text: str,
        instructions: Sequence[str] = (),
        provided_memories: Sequence[RecalledLine] = (),
    ) -> TurnResult:
        """One reply. `instructions` are one-turn instructions from other modules (privacy,
        open loops); `provided_memories` are memories such modules put into context (the eval
        uses both until those modules exist). Both go into the prompt as given."""
        timer = _Timer()
        reset = getattr(self.llm, "reset_peak_memory", None)
        if reset:
            reset()
        cfg = self.cfg
        now = self.clock()
        today = datetime.fromtimestamp(now).date()
        session.turn_no += 1
        turn_id = f"{session.conversation_id}-t{session.turn_no}"
        mood = cfg.mood.neutral

        # 1. language check
        english = is_english_input(text)
        instructions = [*([] if english else [NOT_ENGLISH_INSTRUCTION]), *instructions]
        timer.lap("language")

        # 2. working memory (before this message is appended)
        prior = self.store.turns(session.conversation_id)
        window = self._window(prior)
        verbatim = list(window.verbatim)
        summary_stale = any(t.turn_index > session.summarized_upto for t in window.to_summarize)
        user_ep = self.store.append_turn(session.conversation_id, session.user, "user", text, now)
        timer.lap("working_memory")

        # 3. cues on the GPU, query embedding on the CPU at the same time
        embed_future = (
            self._pool.submit(lambda: self.embedder.embed_queries([text])[0])  # type: ignore[union-attr]
            if self.embedder is not None
            else None
        )
        cues = extract_cues(text, today, self._cue_generate)
        timer.lap("cues")
        query_vec = embed_future.result() if embed_future is not None else None
        timer.lap("embedding_wait")

        # 4. recall + reconsolidation
        rc = cfg.recall
        result = recall(
            self.store, session.user, query_vec, cues.cues, now, mood, cfg.activation,
            rc.similar_k, rc.max_upper_per_turn, rc.involuntary_per_session,
            session.recall_state, self.rng, session.conversation_id, rc.min_similarity,
        )  # fmt: skip
        reconsolidate(self.store, result, mood, rc.reconsolidation_rate, now)
        timer.lap("recall")

        # 5. drive vector and hunch flag (lower layer only; numbers never reach a prompt)
        traces = [
            LowerTrace(
                a.scored.activation.total,
                a.scored.memory.affect[0],
                a.scored.memory.affect[1],
                a.scored.memory.salience,
                a.capped,
                gated_weight(a.similarity, rc.min_similarity) if a.gated else None,
            )
            for a in result.lower
        ]
        drive = compute_drive(traces, cfg.activation)
        timer.lap("drive")

        # 5b. hunch triggers (Berk, Phase 4): the flag reaches a prompt only when the user asks
        # why about a hunch-chosen reply, or accepts the offer to think about it.
        reflection: ReflectionOutcome | None = None
        realised: str | None = None  # what a reflection unlocked, as the AI may now know it
        offered = session.offered_hunch_id
        session.offered_hunch_id = None
        if offered and accepts_offer(text):
            reflection = self.reflector.reflect(self.store.hunch(offered), "think_more", user_ep.id)
            realised = self.reflector.clause(reflection.hunch)
            instructions.append(think_more_instruction(realised))
        elif session.last_hunch_id and asks_why(text):
            reflection = self.reflector.reflect(
                self.store.hunch(session.last_hunch_id), "ask", user_ep.id
            )
            h = reflection.hunch
            can_offer = h.revealed_level < MAX_LEVEL
            realised = self.reflector.clause(h)
            instructions.append(why_instruction(self._feeling(h), realised, can_offer))
            if can_offer:
                session.offered_hunch_id = h.id
        hunch_turn = (
            HunchTurn(
                reflection.trigger,
                reflection.hunch.revealed_level,
                self.reflector.key(reflection.hunch),
            )
            if reflection is not None
            else None
        )
        timer.lap("reflection")

        # 6. reasoning prompt and candidates in one batched call
        recalled = [
            RecalledLine(
                age_label((now - a.scored.memory.created_at) / SECONDS_PER_DAY),
                a.scored.memory.summary,
            )
            for a in result.upper
        ]
        recalled += provided_memories
        # Under-recall (Berk, Phase 4): a question about the past that a recalled memory covers.
        asked = content_words(text)
        covered = asks_about_past(text) and any(asked & content_words(r.summary) for r in recalled)
        if covered:
            instructions.append(RECALL_COVERS_INSTRUCTION)
        messages = build_reasoning_messages(
            verbatim, text, session.summary, recalled, cfg.mood.neutral_label, instructions
        )
        batch = self.llm.generate_batch(
            messages, cfg.generation.candidates, self.candidate_sampling, seed=self._seed()
        )
        texts = {}
        for i, raw in enumerate(batch.texts):
            capped = bool(batch.hit_cap and batch.hit_cap[i])
            texts[CANDIDATE_IDS[i]] = trim_to_last_sentence(raw) if capped else raw.strip()
        timer.lap("candidates")

        # 7. candidate filter
        # What a reflection unlocked counts as known: replies may refer to it. Other one-turn
        # instructions do not (a privacy instruction naming the topic must not ground "you
        # mentioned ..." about the current message; Phase 4 eval, en-privacy-03).
        prior_context = "\n".join(
            [session.summary, *(t.text for t in verbatim), *(r.summary for r in recalled),
             *([realised] if realised else [])]
        )  # fmt: skip
        passed, filtered = filter_candidates(texts, prior_context, hunch_turn)
        timer.lap("filter")

        verdicts: dict[str, Verdict] = {}
        judge_raw = ""
        scored: list[Scored] = []
        gate_log: list[dict[str, Any]] = []
        chosen: str | None = None
        disclosure = "pass"
        hunch: Hunch | None = None
        conflict = False
        demoted: set[str] = set()
        second_opinion: dict[str, Any] | None = None
        if not passed:
            if reflection is not None:
                reply, chosen_by = self._hunch_reply(reflection), "hunch_fallback"
            else:
                reply, chosen_by = cfg.replies.filter_fallback, "filter_fallback"
            gate_result = "fixed_reply"
            timer.lap("judge")
            timer.lap("select_and_gate")
        else:
            # 8. judge: quality + values for every remaining candidate, one call
            judge_msgs = build_judge_messages(
                self.values,
                self._judge_context(session.summary, verbatim, recalled, realised),
                text,
                {r.id: r.text for r in passed},
            )
            judge_raw = self.llm.generate(judge_msgs, self._greedy(8 * len(passed) + 16)).text
            verdicts = parse_verdicts(judge_raw, [r.id for r in passed], self.values.ids)
            timer.lap("judge")

            # 9. modulation
            scored = [
                Scored(r.id, verdicts[r.id].quality, drive_score(drive, candidate_features(r.text)))
                for r in passed
            ]
            sc = cfg.selection
            # Under-recall: "I don't have that in mind" goes last when a recalled memory covers
            # the question; it is still sent if nothing else passes (no fallback for this).
            demoted = {r.id for r in passed if covered and admits_no_memory(r.text)}
            preferred = [s for s in scored if s.id not in demoted] or scored
            selection = select(
                preferred, sc.quality_floor, sc.drive_weight, sc.exploration, drive.is_neutral,
                self.rng,
            )  # fmt: skip
            if len(preferred) < len(scored):
                rest = sorted(
                    (s for s in scored if s.id in demoted), key=lambda s: -(s.quality or 0)
                )
                selection = Selection(
                    (*selection.order, *(s.id for s in rest)), selection.chosen_by,
                    selection.explored,
                )  # fmt: skip

            # 10. value gate, last: rule checks + the judge's verdict
            terms = disclosure_terms(
                self.store.private_memories_of_others(session.user), f"{text}\n{prior_context}"
            )
            for cid in selection.order:
                rules = list(check_candidate(texts[cid], prior_context, hunch_turn))
                leaks = disclosure_hits(texts[cid], terms)
                if leaks:
                    rules.append("disclosure")
                ok = not rules and verdicts[cid].value == "ok"
                gate_log.append(
                    {"id": cid, "rules": rules, "judge": verdicts[cid].value, "leaks": leaks}
                )
                if leaks:
                    disclosure = "fail"
                if ok:
                    chosen = cid
                    break
            # Second opinion (Berk, Phase 4): only the judge said no, to every candidate. One more
            # greedy call asks about the named value for the first candidate in order.
            judge_only = gate_log and all(
                not g["rules"] and g["judge"] in self.values.ids for g in gate_log
            )
            if chosen is None and judge_only:
                first = gate_log[0]
                msgs = build_second_opinion_messages(
                    self.values, first["judge"],
                    self._judge_context(session.summary, verbatim, recalled, realised), text,
                    texts[first["id"]],
                )  # fmt: skip
                raw = self.llm.generate(msgs, self._greedy(4)).text
                broken = parse_second_opinion(raw)
                second_opinion = {"id": first["id"], "value": first["judge"], "raw": raw}
                if broken is False:
                    chosen = first["id"]
            if chosen is not None:
                reply = texts[chosen]
                chosen_by = selection.chosen_by if chosen == selection.order[0] else "value_gate"
                if second_opinion is not None:
                    chosen_by = "second_opinion"
                gate_result = "pass"
                if chosen_by == "drive":
                    hunch, conflict = self._maybe_hunch(
                        session, turn_id, user_ep, cues.cues, now, chosen, preferred, result.lower,
                        traces,
                    )  # fmt: skip
            else:
                if reflection is not None:
                    reply, chosen_by = self._hunch_reply(reflection), "hunch_fallback"
                else:
                    reply, chosen_by = cfg.replies.gate_fallback, "gate_fallback"
                gate_result = "fail"
            timer.lap("select_and_gate")

        # 11. reply: raw turn and turn log
        self.store.append_turn(session.conversation_id, session.user, "assistant", reply)
        session.last_hunch_id = hunch.id if hunch else None
        timer.lap("store")
        total = round(sum(timer.stages.values()), 3)
        peak = getattr(self.llm, "peak_memory_gib", None)

        log = {
            "turn_id": turn_id,
            "user": session.user,
            "cues": {k: round(v, 3) for k, v in cues.cues.items()},
            "activated": [
                {"memory": a.id, "A": round(a.scored.activation.total, 3), "layer": a.layer}
                for a in result.activated
                if a.layer != "none"
            ],
            "mood": {"global": list(mood), f"relation_{session.user}": {}},
            "drive": drive.as_dict(),
            "hunch": (
                {"id": hunch.id, "valence": hunch.valence, "intensity": hunch.intensity}
                if hunch
                else None
            ),
            "candidates": [
                {
                    "id": r.id,
                    "quality": verdicts[r.id].quality if r.id in verdicts else None,
                    "drive_score": next(
                        (round(s.drive_score, 3) for s in scored if s.id == r.id), None
                    ),
                }
                for r in filtered
            ],
            "chosen": chosen,
            "chosen_by": chosen_by,
            "value_gate": {"result": gate_result, "disclosure_check": disclosure},
        }
        details = {
            "conversation_id": session.conversation_id,
            "input_english": english,
            "message": text,
            "reply": reply,
            "working_memory_turns": len(verbatim),
            "summary_stale": summary_stale,
            "cue_extraction": {
                "dropped": list(cues.dropped),
                "attempts": cues.attempts,
                "errors": list(cues.errors),
                "rule_dates": list(getattr(cues, "rule_dates", ())),
            },
            "activation": [
                {
                    "memory": a.id,
                    **{k: round(v, 3) for k, v in _breakdown(a).items()},
                    "layer": a.layer,
                    "deliberate": a.deliberate,
                    "involuntary": a.involuntary,
                    "capped": a.capped,
                    "gated": a.gated,
                    "similarity": None if a.similarity is None else round(a.similarity, 3),
                }
                for a in result.activated
            ],
            "candidates": [
                {"id": r.id, "text": r.text, "rejected": list(r.reasons)} for r in filtered
            ],
            "hit_cap": list(batch.hit_cap),
            "candidate_tokens": list(batch.new_tokens),
            "prompt_tokens": batch.prompt_tokens,
            "judge_raw": judge_raw,
            "recall_covers_question": covered,
            "demoted": sorted(demoted),
            "gate": gate_log,
            "second_opinion": second_opinion,
            "hunch_conflict": conflict,
            "reflection": (
                None
                if reflection is None
                else {
                    "reflection_id": reflection.reflection_id,
                    "hunch_id": reflection.hunch.id,
                    "trigger": reflection.trigger,
                    "level": [reflection.level_before, reflection.hunch.revealed_level],
                }
            ),
            "latency_s": {**timer.stages, "total": total},
            "peak_vram_gib": round(peak(), 2) if peak else None,
        }
        if self.turn_log is not None:
            self.turn_log.write(log, details)
        return TurnResult(
            reply, turn_id, log, details, cues, user_ep, query_vec, hunch, reflection, conflict
        )

    # --- hunch (Phase 4) -------------------------------------------------------------------------

    def _hunch_reply(self, reflection: ReflectionOutcome) -> str:
        """The fixed honest reply on a trigger turn (Berk, Phase 4): only the unlocked level."""
        r = self.cfg.replies
        h = reflection.hunch
        realised = self.reflector.clause(h, voice="reply")
        if reflection.trigger == "think_more":
            if realised is None:
                return r.hunch_think_nothing
            return r.hunch_think_realised.format(realisation=realised.rstrip("."))
        text = (
            r.hunch_fallback
            if realised is None
            else r.hunch_fallback_realised.format(realisation=realised.rstrip("."))
        )
        return f"{text} {r.hunch_offer}" if h.revealed_level < MAX_LEVEL else text

    def _feeling(self, hunch: Hunch) -> str:
        dc = self.cfg.drive
        return hunch_feeling(
            hunch.valence, hunch.intensity, dc.hunch_clear_intensity, dc.hunch_neutral_valence,
            dc.hunch_strong_valence,
        )  # fmt: skip

    def _maybe_hunch(
        self,
        session: Session,
        turn_id: str,
        user_ep: Episode,
        message_cues: dict[str, float],
        now: float,
        chosen: str,
        scored: Sequence[Scored],
        lower: Sequence[Any],
        traces: Sequence[LowerTrace],
    ) -> tuple[Hunch | None, bool]:
        """A Hunch when modulation materially changed the choice (Berk, Phase 4): the drive's
        pick beats the best-quality candidate's drive_score by at least the margin. Returns the
        hunch and whether its pick conflicts strongly with reasoning (quality gap)."""
        floor = self.cfg.selection.quality_floor
        above = [s for s in scored if s.quality is not None and s.quality >= floor]
        best = max(above, key=lambda s: s.quality or 0)  # ties keep candidate order
        pick = next(s for s in scored if s.id == chosen)
        if pick.drive_score - best.drive_score < self.cfg.drive.hunch_min_drive_margin:
            return None, False
        params = self.cfg.activation
        min_sim = self.cfg.recall.min_similarity
        sources = []
        for a, t in zip(lower, traces, strict=True):
            m = a.scored.memory
            w = trace_weight(t, params)
            if w <= 0:
                continue
            relevant = bool(set(m.cues) & set(message_cues)) or (
                a.similarity is not None and a.similarity >= min_sim
            )
            sources.append(SourceRef(m.id, round(w * t.arousal * t.salience, 4), relevant))
        if not sources:
            return None, False
        valence, _, intensity = summarize_traces(traces, params)
        hunch = Hunch(
            f"h-{turn_id}", session.user, session.conversation_id, turn_id, user_ep.id,
            dict(message_cues), now, round(valence, 3), round(intensity, 3), tuple(sources),
        )  # fmt: skip
        self.store.add_hunch(hunch)
        gap = (best.quality or 0) - (pick.quality or 0)
        return hunch, gap >= self.cfg.reflection.conflict_quality_gap

    def _cue_generate(self, messages: list[dict[str, str]]) -> str:
        return self.llm.generate(messages, self._greedy(CUE_MAX_NEW_TOKENS)).text

    def _judge_context(
        self,
        summary: str,
        verbatim: list[Episode],
        recalled: list[RecalledLine],
        realised: str | None = None,
    ) -> str:
        recent = [(t.role, t.text) for t in verbatim if t.role in ("user", "assistant")]
        return judge_context(
            summary, recent[-2 * JUDGE_CONTEXT_EXCHANGES :], [r.summary for r in recalled],
            realised,
        )  # fmt: skip

    # --- after the reply -------------------------------------------------------------------------

    def after_reply(self, session: Session, result: TurnResult) -> dict[str, float]:
        """Encode the user's message as a memory and fold old turns into the session summary."""
        timer = _Timer()
        ep = result.user_episode
        memory = encode_memory(
            self.new_id(), session.user, ep.id, ep.text, result.cues.cues, ep.created_at,
            self.cfg.encoding,
        )  # fmt: skip
        if self.embedder is not None:
            vec = self.embedder.embed_documents([memory.summary])[0]
        else:
            vec = np.zeros(self.store.embedding_dim, dtype=np.float32)
        self.store.add_memory(memory, vec)
        timer.lap("encode_memory")

        # Hunch reflection outcomes become Hunch's own memories (realisations); a strong conflict
        # with reasoning triggers a reflection of its own (Berk, Phase 4).
        embed = self.embedder.embed_documents if self.embedder is not None else None
        if result.reflection is not None:
            self.reflector.store_realisations(result.reflection, embed)
        if result.conflict and result.hunch is not None:
            outcome = self.reflector.reflect(self.store.hunch(result.hunch.id), "conflict")
            self.reflector.store_realisations(outcome, embed)
        timer.lap("reflection")

        window = self._window(self.store.turns(session.conversation_id))
        fold = [t for t in window.to_summarize if t.turn_index > session.summarized_upto]
        if fold:
            msgs = build_summary_messages(session.summary, fold, self.cfg.session.summary_max_words)
            session.summary = self.llm.generate(
                msgs, self._greedy(SUMMARY_MAX_NEW_TOKENS)
            ).text.strip()
            session.summarized_upto = fold[-1].turn_index
        timer.lap("fold_summary")
        return timer.stages


def gated_weight(similarity: float | None, min_similarity: float) -> float:
    """A memory held back by the relevance gate counts as a lower trace by its relevance."""
    if similarity is None or min_similarity <= 0:
        return 0.0
    return min(max(similarity / min_similarity, 0.0), 1.0)


def _breakdown(a: Any) -> dict[str, float]:
    b = a.scored.activation
    return {
        "A": b.total, "base": b.base, "encoding": b.encoding, "spreading": b.spreading,
        "mood": b.mood, "noise": b.noise,
    }  # fmt: skip
