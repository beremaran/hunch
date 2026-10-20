"""Involuntary recall (design.md, "İstemsiz hatırlama").

A memory comes up involuntarily when it crosses tau_upper only thanks to the cues of the current
message, without the AI looking for it: it was not among the memories retrieved on purpose, and
without its spreading activation it would have stayed below tau_upper ("this song reminded me of
something"). Their number is capped per session (conversation).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from hunch.memory.schema import Memory
from hunch.recall.activation import ActivationBreakdown, ActivationParams, layer


@dataclass(frozen=True, slots=True)
class ScoredMemory:
    memory: Memory
    activation: ActivationBreakdown


@dataclass(slots=True)
class SessionRecallState:
    """Per-conversation bookkeeping; lives as long as the session."""

    involuntary_used: int = 0


def is_involuntary(
    scored: ScoredMemory, deliberate_ids: set[str], params: ActivationParams
) -> bool:
    a = scored.activation
    return (
        scored.memory.id not in deliberate_ids
        and layer(a.total, params, suppressed=scored.memory.suppressed) == "upper"
        and a.spreading > 0
        and a.total - a.spreading <= params.tau_upper  # the cue made the difference
    )


def select_involuntary(
    scored: Iterable[ScoredMemory],
    deliberate_ids: set[str],
    params: ActivationParams,
    cap_per_session: int,
    state: SessionRecallState,
) -> list[ScoredMemory]:
    """The strongest involuntary recalls this turn, within what is left of the session cap."""
    left = max(cap_per_session - state.involuntary_used, 0)
    if left == 0:
        return []
    picked = sorted(
        (s for s in scored if is_involuntary(s, deliberate_ids, params)),
        key=lambda s: s.activation.total,
        reverse=True,
    )[:left]
    state.involuntary_used += len(picked)
    return picked
