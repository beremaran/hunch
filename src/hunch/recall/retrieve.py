"""The recall step of a turn: which memories enter reasoning and which act only from below.

1. Candidates: the similar_k nearest memories by embedding (retrieved on purpose, "deliberate")
   plus every memory that shares a cue with the message; only the user's own memories and other
   users' general ones (invariant 6). Memories encoded from the current conversation are left
   out: the working memory and the session summary already hold them, and design.md keeps "just
   said" apart from "recalled from the past".
2. Activation for each candidate (hunch.recall.activation).
3. Relevance gate (Berk): only a memory that shares a cue with the message or whose embedding
   similarity to the message is at least min_similarity may enter reasoning; a gated memory above
   tau_upper acts as a lower trace instead.
   Upper layer: above tau_upper, strongest first, at most max_upper_per_turn. A memory that only
   crossed tau_upper thanks to the message's cues and was not retrieved on purpose is an
   involuntary recall; those count against the per-session cap and are dropped to the lower
   layer once it is used up.
4. Memories above tau_upper that did not fit act as lower traces ("capped"); memories between
   tau_lower and tau_upper are lower traces. Only the upper ones count as recalled: they get
   reconsolidated (an access is logged and their affect drifts toward the mood).
5. Mediation (Berk, Phase 5): other users' private memories the caller found (shared cue or close
   by embedding) are scored too, but never get above the lower layer, like a suppressed memory:
   they shape the drive and nothing else. A suppressed memory of this user that would otherwise
   have entered reasoning is flagged `closed`, so the pipeline can say "we closed that one".
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from hunch.memory.schema import Memory
from hunch.memory.store import MemoryStore
from hunch.recall.activation import ActivationParams, activation, layer
from hunch.recall.involuntary import ScoredMemory, SessionRecallState, is_involuntary
from hunch.recall.reconsolidation import recall_memory


@dataclass(frozen=True, slots=True)
class Activated:
    scored: ScoredMemory
    layer: str  # "upper" | "lower" | "none"
    deliberate: bool
    involuntary: bool = False
    capped: bool = False  # above tau_upper but did not fit into the per-turn cap
    gated: bool = False  # above tau_upper but not relevant to the message (relevance gate)
    similarity: float | None = None  # cosine to the message, if retrieved by embedding
    mediated: bool = False  # another user's private memory: never above the lower layer
    closed: bool = False  # suppressed by this user, but relevant and above tau_upper

    @property
    def id(self) -> str:
        return self.scored.memory.id


@dataclass(frozen=True, slots=True)
class RecallResult:
    activated: tuple[Activated, ...]  # every candidate, strongest first

    @property
    def upper(self) -> list[Activated]:
        return [a for a in self.activated if a.layer == "upper"]

    @property
    def lower(self) -> list[Activated]:
        return [a for a in self.activated if a.layer == "lower"]


def recall(
    store: MemoryStore,
    user: str,
    query_vec: np.ndarray | None,
    message_cues: Mapping[str, float],
    now: float,
    mood: tuple[float, float],
    params: ActivationParams,
    similar_k: int,
    max_upper: int,
    involuntary_cap: int,
    session: SessionRecallState,
    rng: np.random.Generator,
    conversation_id: str | None = None,
    min_similarity: float = -1.0,
    mediated: Sequence[tuple[Memory, float | None]] = (),
) -> RecallResult:
    own = store.memory_ids_from_conversation(conversation_id) if conversation_id else set()
    deliberate: dict[str, object] = {}
    similarity: dict[str, float] = {}
    if query_vec is not None:
        for m, distance in store.similar(query_vec, similar_k + len(own), visible_to=user):
            if m.id not in own and len(deliberate) < similar_k:
                deliberate[m.id] = m
                similarity[m.id] = 1.0 - distance  # cosine distance -> similarity
    candidates = dict(deliberate)
    for m in store.with_cues(message_cues, visible_to=user):
        if m.id not in own:
            candidates.setdefault(m.id, m)
    others: set[str] = set()
    for m, sim in mediated:
        if m.owner_user != user and m.privacy == "private" and m.id not in candidates:
            candidates[m.id] = m
            others.add(m.id)
            if sim is not None:
                similarity[m.id] = sim

    fan = store.cue_fan
    scored = [
        ScoredMemory(m, activation(m, now, message_cues, fan, mood, params, rng))  # type: ignore[arg-type]
        for m in candidates.values()
    ]
    scored.sort(key=lambda s: s.activation.total, reverse=True)

    deliberate_ids = set(deliberate)
    involuntary_left = max(involuntary_cap - session.involuntary_used, 0)
    upper_left = max_upper
    out: list[Activated] = []
    for s in scored:
        mid = s.memory.id
        mediated_here = mid in others
        held = s.memory.suppressed or mediated_here
        base_layer = layer(s.activation.total, params, suppressed=held)
        is_deliberate = mid in deliberate_ids
        sim = similarity.get(mid)
        relevant = bool(set(message_cues) & set(s.memory.cues)) or (
            sim is not None and sim >= min_similarity
        )
        if base_layer != "upper":
            closed = (
                s.memory.suppressed
                and not mediated_here
                and relevant
                and layer(s.activation.total, params) == "upper"
            )
            out.append(
                Activated(s, base_layer, is_deliberate, similarity=sim, mediated=mediated_here,
                          closed=closed)
            )  # fmt: skip
            continue
        if not relevant:
            out.append(Activated(s, "lower", is_deliberate, gated=True, similarity=sim))
            continue
        involuntary = is_involuntary(s, deliberate_ids, params)
        if upper_left == 0 or (involuntary and involuntary_left == 0):
            out.append(Activated(s, "lower", is_deliberate, involuntary, True, similarity=sim))
            continue
        upper_left -= 1
        if involuntary:
            involuntary_left -= 1
            session.involuntary_used += 1
        out.append(Activated(s, "upper", is_deliberate, involuntary, similarity=sim))
    return RecallResult(tuple(out))


def reconsolidate(
    store: MemoryStore, result: RecallResult, mood: tuple[float, float], rate: float, now: float
) -> None:
    """Every memory that entered reasoning was recalled: rehearse it and drift its affect."""
    for a in result.upper:
        recall_memory(store, a.id, mood, rate, at=now)
