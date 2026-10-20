"""The turn pipeline (design.md, "Mimari genel bakış"; Phase 3).

Reply path, in this order (invariant 4: the value gate is always last):
  1. "is the input English?" check -> one-turn instruction if not
  2. working memory: last N exchanges verbatim + rolling session summary
  3. cue extraction (LLM + rule-based dates); the query embedding runs on CPU in parallel
  4. activation over the candidates: upper memories enter reasoning, lower ones only act below;
     every recall is reconsolidated
  5. drive vector and hunch flag from the lower traces
  6. reasoning prompt -> all candidates in one batched call
  7. candidate filter (all fail -> fixed fallback reply)
  8. judge: quality and core values for the remaining candidates, one greedy call
  9. modulation: selection above the quality floor, small exploration
 10. value gate on the chosen candidate (rule checks + judge verdict), then the next ones
 11. reply; raw turns appended, turn log written
After the reply (off the latency path): the user's message is encoded as a memory and turns that
left the working memory are folded into the session summary.

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
from typing import Any

import numpy as np

from hunch.config import Config
from hunch.drive.drive import (
    LowerTrace,
    candidate_features,
    compute_drive,
    drive_score,
    hunch_flag,
)
from hunch.drive.modulation import Scored, select
from hunch.llm.types import ChatLLM, SamplingSettings
from hunch.memory.embeddings import Embedder
from hunch.memory.encoding import encode_memory
from hunch.memory.schema import Episode
from hunch.memory.store import MemoryStore, select_working_memory
from hunch.observability.turn_log import TurnLog
from hunch.pipeline.checks import is_english_input
from hunch.pipeline.filter import check_candidate, filter_candidates, trim_to_last_sentence
from hunch.pipeline.prompt import (
    NOT_ENGLISH_INSTRUCTION,
    RecalledLine,
    age_label,
    build_reasoning_messages,
    build_summary_messages,
    hunch_words,
)
from hunch.recall.activation import SECONDS_PER_DAY
from hunch.recall.cues import CueExtraction, extract_cues
from hunch.recall.involuntary import SessionRecallState
from hunch.recall.retrieve import recall, reconsolidate
from hunch.values.core import CoreValues
from hunch.values.gate import (
    Verdict,
    build_judge_messages,
    disclosure_hits,
    disclosure_terms,
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


@dataclass(frozen=True)
class TurnResult:
    reply: str
    turn_id: str
    log: dict[str, Any]  # the design.md turn log record
    details: dict[str, Any]  # admin details: texts, reasons, latency
    cues: CueExtraction
    user_episode: Episode
    query_vec: np.ndarray | None


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
        dc = cfg.drive
        flag = hunch_flag(traces, cfg.activation, dc.hunch_min_intensity, f"h-{turn_id}")
        hunch_text = (
            hunch_words(
                flag, dc.hunch_clear_intensity, dc.hunch_neutral_valence, dc.hunch_strong_valence
            )
            if flag
            else None
        )
        timer.lap("drive")

        # 6. reasoning prompt and candidates in one batched call
        recalled = [
            RecalledLine(
                age_label((now - a.scored.memory.created_at) / SECONDS_PER_DAY),
                a.scored.memory.summary,
            )
            for a in result.upper
        ]
        recalled += provided_memories
        messages = build_reasoning_messages(
            verbatim, text, session.summary, recalled, cfg.mood.neutral_label, hunch_text,
            instructions,
        )  # fmt: skip
        batch = self.llm.generate_batch(
            messages, cfg.generation.candidates, self.candidate_sampling, seed=self._seed()
        )
        texts = {}
        for i, raw in enumerate(batch.texts):
            capped = bool(batch.hit_cap and batch.hit_cap[i])
            texts[CANDIDATE_IDS[i]] = trim_to_last_sentence(raw) if capped else raw.strip()
        timer.lap("candidates")

        # 7. candidate filter
        prior_context = "\n".join(
            [session.summary, *(t.text for t in verbatim), *(r.summary for r in recalled)]
        )
        passed, filtered = filter_candidates(texts, prior_context)
        timer.lap("filter")

        verdicts: dict[str, Verdict] = {}
        judge_raw = ""
        scored: list[Scored] = []
        gate_log: list[dict[str, Any]] = []
        chosen: str | None = None
        disclosure = "pass"
        if not passed:
            reply = cfg.replies.filter_fallback
            chosen_by = "filter_fallback"
            gate_result = "fixed_reply"
            timer.lap("judge")
            timer.lap("select_and_gate")
        else:
            # 8. judge: quality + values for every remaining candidate, one call
            judge_msgs = build_judge_messages(
                self.values,
                self._judge_context(session.summary, verbatim, recalled),
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
            selection = select(
                scored, sc.quality_floor, sc.drive_weight, sc.exploration, drive.is_neutral,
                self.rng,
            )  # fmt: skip

            # 10. value gate, last: rule checks + the judge's verdict
            terms = disclosure_terms(
                self.store.private_memories_of_others(session.user), f"{text}\n{prior_context}"
            )
            for cid in selection.order:
                rules = list(check_candidate(texts[cid], prior_context))
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
            if chosen is not None:
                reply = texts[chosen]
                chosen_by = selection.chosen_by if chosen == selection.order[0] else "value_gate"
                gate_result = "pass"
            else:
                reply = cfg.replies.gate_fallback
                chosen_by = "gate_fallback"
                gate_result = "fail"
            timer.lap("select_and_gate")

        # 11. reply: raw turn and turn log
        self.store.append_turn(session.conversation_id, session.user, "assistant", reply)
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
                {"id": flag.id, "valence": flag.valence, "intensity": flag.intensity}
                if flag
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
            "gate": gate_log,
            "latency_s": {**timer.stages, "total": total},
            "peak_vram_gib": round(peak(), 2) if peak else None,
        }
        if self.turn_log is not None:
            self.turn_log.write(log, details)
        return TurnResult(reply, turn_id, log, details, cues, user_ep, query_vec)

    def _cue_generate(self, messages: list[dict[str, str]]) -> str:
        return self.llm.generate(messages, self._greedy(CUE_MAX_NEW_TOKENS)).text

    def _judge_context(
        self, summary: str, verbatim: list[Episode], recalled: list[RecalledLine]
    ) -> str:
        parts = []
        if recalled:
            parts.append(
                "Memories Hunch recalled:\n" + "\n".join(f"- {r.summary}" for r in recalled)
            )
        if summary:
            parts.append(f"Summary of the earlier conversation:\n{summary}")
        recent = [t for t in verbatim if t.role in ("user", "assistant")]
        recent = recent[-2 * JUDGE_CONTEXT_EXCHANGES :]
        if recent:
            lines = "\n".join(
                f"{'User' if t.role == 'user' else 'Hunch'}: {t.text}" for t in recent
            )
            parts.append(f"Conversation so far:\n{lines}")
        return "\n\n".join(parts)

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
