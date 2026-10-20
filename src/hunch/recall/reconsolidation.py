"""Reconsolidation (design.md, "Yeniden konsolidasyon").

Every recall shifts the memory's affect slightly toward the current mood. The raw episode never
changes; only the memory of it does, and every shift is logged, so the difference between the
record and its memory stays visible (for reflection and the admin).
"""

from __future__ import annotations

from hunch.memory.store import MemoryStore


def drift_affect(
    affect: tuple[float, float], mood: tuple[float, float], rate: float
) -> tuple[float, float]:
    """Move (valence, arousal) a fraction `rate` of the way toward the mood, within range."""
    if not 0 <= rate <= 1:
        raise ValueError("rate must be in [0, 1]")
    v = affect[0] + rate * (mood[0] - affect[0])
    a = affect[1] + rate * (mood[1] - affect[1])
    return (min(max(v, -1.0), 1.0), min(max(a, 0.0), 1.0))


def recall_memory(
    store: MemoryStore,
    memory_id: str,
    mood: tuple[float, float],
    rate: float,
    at: float | None = None,
) -> tuple[float, float]:
    """A memory was recalled: log the access (rehearsal) and drift its affect toward the mood."""
    memory = store.memory(memory_id)
    store.record_access(memory_id, at=at)
    new_affect = drift_affect(memory.affect, mood, rate)
    store.update_affect(memory_id, new_affect, reason="reconsolidation", at=at)
    return new_affect
