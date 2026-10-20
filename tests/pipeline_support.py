"""Shared helpers for the turn pipeline tests (fixtures live in conftest.py)."""

from __future__ import annotations

import numpy as np

from hunch.memory.schema import Memory
from hunch.memory.store import MemoryStore
from tests.fakes import HashEmbedder

DAY = 86_400.0
NOW = 1_800_000_000.0  # 2027-01-15
DIM = 16
FALLBACK = "I don't have that in mind right now. Could you tell me again?"


class Clock:
    def __init__(self) -> None:
        self.t = NOW

    def __call__(self) -> float:
        self.t += 1.0
        return self.t


def seed_memory(
    store: MemoryStore,
    mid: str,
    summary: str,
    cues: dict[str, float],
    age_days: float,
    owner: str = "u_berk",
    privacy: str = "private",
    affect: tuple[float, float] = (0.0, 0.5),
    salience: float = 0.2,
    vec: np.ndarray | None = None,
) -> Memory:
    ep = store.append_turn(f"old-{mid}", owner, "user", summary, at=NOW - age_days * DAY)
    m = Memory(mid, owner, privacy, ep.id, summary, cues, affect, salience, NOW - age_days * DAY)  # type: ignore[arg-type]
    store.add_memory(m, HashEmbedder(DIM).embed_documents([summary])[0] if vec is None else vec)
    return m


def unit(i: int) -> np.ndarray:
    v = np.zeros(DIM, dtype=np.float32)
    v[i] = 1.0
    return v


class KeywordEmbedder:
    """Queries point along unit(0) if they contain the keyword, else along unit(1)."""

    def __init__(self, keyword: str) -> None:
        self.keyword = keyword
        self.dim = DIM

    def _vec(self, text: str) -> np.ndarray:
        return unit(0) if self.keyword in text.casefold() else unit(1)

    def embed_documents(self, texts):
        return np.stack([self._vec(t) for t in texts])

    def embed_queries(self, texts):
        return self.embed_documents(texts)
