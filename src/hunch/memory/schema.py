"""Records of the memory layers (design.md, "Hafıza katmanları").

Episode: one raw turn of a conversation, append-only (invariant 1).
Memory: the dual-coded memory derived from an episode: an upper trace (summary) that may enter
reasoning and a lower trace (cues, affect, salience) that only ever shapes behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Privacy = Literal["private", "general"]
Role = Literal["user", "assistant"]
PRIVACY_LEVELS: tuple[str, ...] = ("private", "general")
# episode: encoded from a user message; realisation: what a hunch reflection unlocked (Phase 4),
# Hunch's own memory, at the unlocked level only.
MemoryKind = Literal["episode", "realisation"]
MEMORY_KINDS: tuple[str, ...] = ("episode", "realisation")

# Cue keys are "type:value", e.g. "person:anna", "song:hallelujah" (design.md turn log format).
CUE_TYPES: tuple[str, ...] = ("person", "place", "song", "film", "date", "emotion", "phrase")


def cue_type(cue: str) -> str:
    kind, sep, value = cue.partition(":")
    if not sep or kind not in CUE_TYPES or not value:
        raise ValueError(f"cue must be 'type:value' with type in {CUE_TYPES}, got {cue!r}")
    return kind


@dataclass(frozen=True, slots=True)
class Episode:
    """One raw turn. Never updated or deleted."""

    id: str
    conversation_id: str
    turn_index: int
    owner_user: str  # the person this conversation is with
    role: Role
    text: str
    created_at: float  # unix seconds


@dataclass(frozen=True, slots=True)
class Memory:
    id: str
    owner_user: str  # who told it
    privacy: Privacy
    episode_ref: str  # Episode.id of the raw record
    summary: str  # upper trace
    cues: dict[str, float]  # cue -> bond strength in [0, 1] (lower trace)
    affect: tuple[float, float]  # valence in [-1, 1], arousal in [0, 1] (lower trace)
    salience: float  # importance in [0, 1] (lower trace)
    created_at: float  # unix seconds; the first "access" for base-level activation
    access_times: tuple[float, ...] = field(default_factory=tuple)  # later recalls, unix seconds
    suppressed: bool = False  # user "forget": pretend to have forgotten
    kind: MemoryKind = "episode"
    category: str | None = None  # sensitive topic category (Phase 5 privacy module), if any

    def __post_init__(self) -> None:
        if self.privacy not in PRIVACY_LEVELS:
            raise ValueError(f"privacy must be one of {PRIVACY_LEVELS}, got {self.privacy!r}")
        if self.kind not in MEMORY_KINDS:
            raise ValueError(f"kind must be one of {MEMORY_KINDS}, got {self.kind!r}")
        if not self.owner_user:
            raise ValueError("owner_user is required")
        valence, arousal = self.affect
        if not (-1.0 <= valence <= 1.0 and 0.0 <= arousal <= 1.0):
            raise ValueError(f"affect must be (valence in [-1,1], arousal in [0,1]): {self.affect}")
        if not 0.0 <= self.salience <= 1.0:
            raise ValueError(f"salience must be in [0, 1], got {self.salience}")
        for cue, bond in self.cues.items():
            cue_type(cue)
            if not 0.0 <= bond <= 1.0:
                raise ValueError(f"cue bond for {cue!r} must be in [0, 1], got {bond}")
