"""Records of the hunch layer (design.md, "Hunch ve yansıtma"; Phase 4).

Hunch: created when modulation materially changed the choice of reply. Its source refs point at
the lower traces that shaped the drive; they are sealed: only hunch.reflection.reflect reads
them, and nothing about them reaches a prompt except what a reflection unlocks, as a
realisation, at the unlocked level (invariant 2).

Belief: what a justified source becomes (confidence + evidence ids, admin-visible; the AI sees
the belief only through its realisation memory).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Verdict = Literal["justified", "unjustified"]
MAX_LEVEL = 3  # 0: only the feeling, 1: coarse category, 2: the cue, 3: the full memory


@dataclass(frozen=True, slots=True)
class SourceRef:
    memory_id: str
    strength: float  # trace weight x arousal x salience when the hunch formed
    relevant: bool  # shared a cue with the message, or similarity >= recall.min_similarity


@dataclass(frozen=True, slots=True)
class Hunch:
    id: str
    owner_user: str  # the person the conversation was with
    conversation_id: str
    turn_id: str
    episode_ref: str  # the user message the hunch acted on
    message_cues: dict[str, float]  # that message's own cues
    created_at: float
    valence: float
    intensity: float
    _source_refs: tuple[SourceRef, ...] = field(repr=False)
    revealed_level: int = 0
    verdict: Verdict | None = None

    def __post_init__(self) -> None:
        if not 0 <= self.revealed_level <= MAX_LEVEL:
            raise ValueError(f"revealed_level must be in [0, {MAX_LEVEL}]")

    @property
    def dominant_source(self) -> SourceRef | None:
        """Reflection always targets the strongest source (Berk, Phase 4)."""
        return max(self._source_refs, key=lambda s: s.strength, default=None)


@dataclass(frozen=True, slots=True)
class Belief:
    id: str
    owner_user: str
    text: str
    confidence: float
    evidence: tuple[str, ...]  # memory ids, admin only
    hunch_id: str
    created_at: float
