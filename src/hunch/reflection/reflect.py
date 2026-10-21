"""Graded hunch reflection (design.md, "Hunch ve yansıtma"; Berk, Phase 4).

Each attempt tries to unlock the next level of a hunch's dominant source:
  0 only the feeling, 1 a coarse category ("someone"), 2 the cue ("Anna"), 3 the full memory.
  p = effort x level_difficulty[next] x sqrt(strength) / (1 + age_days / age_scale_days),
  0 below min_strength, at most max_p; drawn from a seeded RNG.
Triggers and their effort: the user asks why (ask), accepts "want me to think about it?"
(think_more), a strong conflict with reasoning (conflict, after the reply), the nightly run
(nightly, up to nightly_attempts levels, stopping at the first failure; Phase 7 schedules it).

Privacy caps (Berk): another user's private memory never unlocks past level 0. A suppressed
memory (user "forget") never reaches reasoning, and a missing one has nothing to reveal: both
stay at 0 too.

At level 3 the source is judged by rule (Berk): justified = relevant to the message the hunch
acted on AND corroborated by another visible memory sharing a named cue with the same valence
sign. Justified -> a belief; unjustified -> the source's salience and arousal are weakened.

What a reflection unlocks becomes Hunch's own memory (kind "realisation"), at the unlocked level
only, so it can later say what it realised and that it changed its mind. The reflection log
(source ids, strengths, probabilities, draws, failed attempts) is for the admin only and never
reaches a prompt (invariants 2 and 7).
"""

from __future__ import annotations

import math
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from typing import Any, Literal

import numpy as np

from hunch.config import EncodingConfig, ReflectionConfig
from hunch.memory.encoding import encode_salience
from hunch.memory.schema import Memory
from hunch.memory.store import MemoryStore
from hunch.observability.turn_log import ReflectionLog
from hunch.pipeline.prompt import age_label
from hunch.recall.activation import SECONDS_PER_DAY
from hunch.reflection.records import MAX_LEVEL, Belief, Hunch, SourceRef

Trigger = Literal["ask", "think_more", "conflict", "nightly"]
TRIGGERS: tuple[str, ...] = ("ask", "think_more", "conflict", "nightly")

_NAMED = ("person", "song", "film", "place", "date", "phrase")  # preference order for ties
_CATEGORY = {
    "person": "someone", "song": "a song", "film": "a film", "place": "a place",
    "date": "a particular day", "phrase": "something that was said",
}  # fmt: skip
# The word a level-1 reply must contain to pass the category on.
_CATEGORY_KEY = {
    "person": "someone", "song": "song", "film": "film", "place": "place", "date": "day",
    "phrase": "said",
}  # fmt: skip
_MESSAGE_CHARS = 120


@dataclass(frozen=True, slots=True)
class Attempt:
    from_level: int
    p: float
    draw: float | None  # None: no draw (capped or nothing to unlock)
    unlocked: bool


@dataclass(frozen=True)
class ReflectionOutcome:
    """What one trigger did. `realisations` are the new memories (not yet stored: the caller
    embeds and stores them, off the latency path); `revealed` is what the AI may now know."""

    reflection_id: str
    hunch: Hunch  # updated: revealed_level, verdict
    trigger: Trigger
    level_before: int
    attempts: tuple[Attempt, ...]
    realisations: tuple[Memory, ...] = field(default_factory=tuple)

    @property
    def unlocked(self) -> bool:
        return self.hunch.revealed_level > self.level_before


def unlock_probability(
    cfg: ReflectionConfig, effort: float, next_level: int, strength: float, age_days: float
) -> float:
    if strength < cfg.min_strength or not 1 <= next_level <= MAX_LEVEL:
        return 0.0
    difficulty = cfg.level_difficulty[next_level - 1]
    p = effort * difficulty * math.sqrt(strength) / (1 + max(age_days, 0.0) / cfg.age_scale_days)
    return min(max(p, 0.0), cfg.max_p)


def level_cap(hunch: Hunch, source: Memory | None) -> int:
    if source is None or source.suppressed:
        return 0
    if source.owner_user != hunch.owner_user and source.privacy == "private":
        return 0
    return MAX_LEVEL


def _effort(cfg: ReflectionConfig, trigger: Trigger) -> float:
    return {
        "ask": cfg.effort_ask, "think_more": cfg.effort_think_more,
        "conflict": cfg.effort_conflict, "nightly": cfg.effort_nightly,
    }[trigger]  # fmt: skip


def dominant_cue(memory: Memory) -> tuple[str, str] | None:
    """(type, value) of the source's strongest named cue, or its strongest emotion."""
    named = [(c, b) for c, b in memory.cues.items() if c.partition(":")[0] in _NAMED]
    pool = named or list(memory.cues.items())
    if not pool:
        return None

    def rank(item: tuple[str, float]) -> tuple[float, int]:
        kind = item[0].partition(":")[0]
        return (-item[1], _NAMED.index(kind) if kind in _NAMED else len(_NAMED))

    kind, _, value = min(pool, key=rank)[0].partition(":")
    return kind, value


def _display(value: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in value.replace("_", " ").split())


def _cue_phrase(kind: str, value: str) -> str:
    shown = _display(value)
    return {
        "person": shown, "place": shown, "song": f'the song "{shown}"',
        "film": f'the film "{shown}"', "date": f"the day {value}",
        "phrase": f'the words "{value.replace("_", " ")}"',
    }.get(kind, f'something that felt "{value.replace("_", " ")}"')  # fmt: skip


def _quote(summary: str) -> str:
    prefix = "They said: "
    return summary[len(prefix) :] if summary.startswith(prefix) else summary


def _category(source: Memory) -> str:
    cue = dominant_cue(source)
    return _CATEGORY.get(cue[0], "an older feeling") if cue else "an older feeling"


def realisation_clause(
    hunch: Hunch,
    source: Memory | None,
    level: int,
    now: float,
    own_user: str,
    voice: str = "ai",
) -> str | None:
    """What the AI knows about its hunch at `level`, and nothing above it. voice "ai" addresses
    Hunch (prompts, realisation memories: "they told you"); voice "reply" is Hunch speaking to
    the user (the fixed asked-why reply: "you told me")."""
    if level <= 0 or source is None:
        return None
    cue = dominant_cue(source)
    if level == 1:
        return f"it seemed to be about {_category(source)}"
    if level == 2:
        return f"it had to do with {_cue_phrase(*cue)}" if cue else "it came from an older feeling"
    age = age_label((now - source.created_at) / SECONDS_PER_DAY)
    own = source.owner_user == own_user
    if voice == "reply":
        who = "you told me" if own else "someone told me"
        fair, unfair = (
            "I think the feeling was fair.",
            "I don't think the feeling was fair, so I let it go and changed my mind.",
        )
    else:
        who = "they told you" if own else "someone told you"
        fair, unfair = (
            "You think the feeling was fair.",
            "You don't think the feeling was fair, so you let it go and changed your mind.",
        )
    clause = f"it came from something {who} {age}: {_quote(source.summary)}"
    if hunch.verdict == "justified":
        return f"{clause} {fair}"
    if hunch.verdict == "unjustified":
        return f"{clause} {unfair}"
    return clause


def revealed_key(source: Memory | None, level: int) -> str | None:
    """The one thing a reply at `level` must pass on: the category at 1 ("someone"), the cue at
    2 ("Mara"); None at 0 and 3 (at 3 the realisation is long; the reason check stays off)."""
    if source is None or level not in (1, 2):
        return None
    cue = dominant_cue(source)
    if level == 1:
        return _CATEGORY_KEY.get(cue[0], "feeling") if cue else "feeling"
    return _display(cue[1]) if cue else None


class Reflector:
    def __init__(
        self,
        cfg: ReflectionConfig,
        store: MemoryStore,
        rng: np.random.Generator,
        feeling: Callable[[Hunch], str],
        encoding_cfg: EncodingConfig,
        log: ReflectionLog | None = None,
        new_id: Callable[[], str] = lambda: uuid.uuid4().hex,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.cfg = cfg
        self.store = store
        self.rng = rng
        self.feeling = feeling
        self.encoding_cfg = encoding_cfg
        self.log = log
        self.new_id = new_id
        self.clock = clock

    def _source(self, ref: SourceRef | None) -> Memory | None:
        if ref is None:
            return None
        try:
            return self.store.memory(ref.memory_id)
        except KeyError:
            return None

    def clause(self, hunch: Hunch, voice: str = "ai") -> str | None:
        """The realisation at the hunch's current level, for a one-turn instruction (voice "ai")
        or the fixed asked-why reply (voice "reply")."""
        source = self._source(hunch.dominant_source)
        return realisation_clause(
            hunch, source, hunch.revealed_level, self.clock(), hunch.owner_user, voice
        )

    def key(self, hunch: Hunch) -> str | None:
        """What a reply at the hunch's current level must pass on (see revealed_key)."""
        return revealed_key(self._source(hunch.dominant_source), hunch.revealed_level)

    def reflect(
        self, hunch: Hunch, trigger: Trigger, episode_ref: str | None = None
    ) -> ReflectionOutcome:
        """One trigger's attempts on `hunch`; updates the store and writes the reflection log.
        `episode_ref` is the message that triggered it (the realisation memories point at it);
        the hunch's own message by default."""
        if trigger not in TRIGGERS:
            raise ValueError(f"unknown trigger {trigger!r}")
        now = self.clock()
        cfg = self.cfg
        ref = hunch.dominant_source
        source = self._source(ref)
        cap = level_cap(hunch, source)
        strength = ref.strength if ref else 0.0
        age_days = (now - source.created_at) / SECONDS_PER_DAY if source else 0.0
        effort = _effort(cfg, trigger)
        n = cfg.nightly_attempts if trigger == "nightly" else 1

        level_before = level = hunch.revealed_level
        attempts: list[Attempt] = []
        for _ in range(n):
            if level >= MAX_LEVEL:
                break
            if level >= cap:
                attempts.append(Attempt(level, 0.0, None, False))
                break
            p = unlock_probability(cfg, effort, level + 1, strength, age_days)
            draw = float(self.rng.random())
            ok = draw < p
            attempts.append(Attempt(level, round(p, 4), round(draw, 4), ok))
            if not ok:
                break
            level += 1

        verdict = hunch.verdict
        evaluation: dict[str, Any] | None = None
        if level == MAX_LEVEL and verdict is None and source is not None:
            verdict, evaluation = self._evaluate(hunch, ref, source, now)
        updated = replace(hunch, revealed_level=level, verdict=verdict)
        if (level, verdict) != (hunch.revealed_level, hunch.verdict):
            self.store.update_hunch(hunch.id, level, verdict)

        realisations = tuple(
            self._realisation(updated, source, lvl, now, episode_ref or hunch.episode_ref)
            for lvl in range(level_before + 1, level + 1)
        )
        outcome = ReflectionOutcome(
            f"r-{self.new_id()[:12]}", updated, trigger, level_before, tuple(attempts),
            realisations,
        )  # fmt: skip
        if self.log is not None:
            self.log.write(self._record(outcome, ref, source, cap, age_days, evaluation, now))
        return outcome

    def nightly(self, since: float) -> list[ReflectionOutcome]:
        """The nightly hook (design.md "Gece konsolidasyonu" step 5; Phase 7 schedules it): the
        day's hunches, high effort. Realisation memories are returned, not stored."""
        return [
            self.reflect(h, "nightly")
            for h in self.store.hunches_since(since)
            if h.revealed_level < MAX_LEVEL
        ]

    # --- level 3: justified or not ---------------------------------------------------------------

    def _evaluate(
        self, hunch: Hunch, ref: SourceRef, source: Memory, now: float
    ) -> tuple[str, dict[str, Any]]:
        cfg = self.cfg
        named = [c for c in source.cues if c.partition(":")[0] in _NAMED]
        sign = _sign(source.affect[0], cfg.corroboration_min_valence)
        corroborating = [
            m.id
            for m in self.store.with_cues(named, visible_to=hunch.owner_user)
            if m.id != source.id
            and m.kind == "episode"
            and not m.suppressed
            and sign != 0
            and _sign(m.affect[0], cfg.corroboration_min_valence) == sign
        ]
        justified = ref.relevant and bool(corroborating)
        record: dict[str, Any] = {
            "relevant": ref.relevant, "corroborating": corroborating,
            "verdict": "justified" if justified else "unjustified",
        }  # fmt: skip
        if justified:
            text = realisation_clause(
                replace(hunch, verdict="justified"), source, MAX_LEVEL, now, hunch.owner_user
            )
            belief = Belief(
                f"b-{self.new_id()[:12]}", hunch.owner_user, f"Your hunch: {text}",
                cfg.belief_confidence, (source.id, *corroborating), hunch.id, now,
            )  # fmt: skip
            self.store.add_belief(belief)
            record["belief"] = belief.id
        else:
            before = (source.salience, source.affect[1])
            after = self.store.weaken_trace(
                source.id, cfg.weaken_factor, f"reflection:{hunch.id}", now
            )
            record["weakened"] = {
                "memory": source.id, "salience": [before[0], after.salience],
                "arousal": [before[1], after.affect[1]],
            }  # fmt: skip
        return record["verdict"], record

    # --- realisation memories --------------------------------------------------------------------

    def _realisation(
        self, hunch: Hunch, source: Memory | None, level: int, now: float, episode_ref: str
    ) -> Memory:
        message = self.store.episode(hunch.episode_ref).text.strip()
        if len(message) > _MESSAGE_CHARS:
            message = message[: _MESSAGE_CHARS - 1].rstrip() + "…"
        clause = realisation_clause(hunch, source, level, now, hunch.owner_user)
        summary = (
            f'You realised: when they said "{message}", you had {self.feeling(hunch)}; '
            f"thinking about it, {clause}."
        ).replace("..", ".")
        cues = dict(hunch.message_cues)
        cue = dominant_cue(source) if source is not None and level >= 2 else None
        if cue:  # the revealed cue links the realisation to future mentions of it
            cues[f"{cue[0]}:{cue[1]}"] = 1.0
        ecfg = self.encoding_cfg
        return Memory(
            id=f"rl-{self.new_id()[:12]}", owner_user=hunch.owner_user, privacy="private",
            episode_ref=episode_ref, summary=summary, cues=cues, affect=ecfg.default_affect,
            salience=encode_salience(cues, ecfg.default_affect[1], ecfg), created_at=now,
            kind="realisation",
        )  # fmt: skip

    def store_realisations(
        self, outcome: ReflectionOutcome, embed: Callable[[Sequence[str]], np.ndarray] | None
    ) -> None:
        if not outcome.realisations:
            return
        texts = [m.summary for m in outcome.realisations]
        vecs = (
            embed(texts)
            if embed is not None
            else np.zeros((len(texts), self.store.embedding_dim), dtype=np.float32)
        )
        for m, v in zip(outcome.realisations, vecs, strict=True):
            self.store.add_memory(m, v)

    # --- admin log -------------------------------------------------------------------------------

    def _record(
        self,
        outcome: ReflectionOutcome,
        ref: SourceRef | None,
        source: Memory | None,
        cap: int,
        age_days: float,
        evaluation: dict[str, Any] | None,
        now: float,
    ) -> dict[str, Any]:
        h = outcome.hunch
        return {
            "reflection_id": outcome.reflection_id,
            "hunch_id": h.id,
            "trigger": outcome.trigger,
            "user": h.owner_user,
            "at": now,
            "source": None if ref is None else {
                "memory": ref.memory_id, "found": source is not None,
                "owner": source.owner_user if source else None,
                "privacy": source.privacy if source else None,
                "strength": round(ref.strength, 4), "relevant": ref.relevant,
                "age_days": round(age_days, 2), "cap": cap,
            },
            "attempts": [
                {"from_level": a.from_level, "p": a.p, "draw": a.draw, "unlocked": a.unlocked}
                for a in outcome.attempts
            ],
            "level_before": outcome.level_before,
            "level_after": h.revealed_level,
            "evaluation": evaluation,
            "realisations": [m.id for m in outcome.realisations],
        }  # fmt: skip


def _sign(valence: float, min_abs: float) -> int:
    if abs(valence) < min_abs:
        return 0
    return 1 if valence > 0 else -1
