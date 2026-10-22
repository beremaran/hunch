"""One open loop per matter (Berk, Phase 6). The model labels the same matter differently each
time the user mentions it ("contract", "getting the new contract"), so a new draft is compared
with the user's open loops by topic embedding. A match is dropped, unless the new draft names a
clock time: then the user gave a (new) date for it, and the draft replaces the old loops."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

from hunch.loops.extract import LoopDraft
from hunch.loops.store import OpenLoop

Embed = Callable[[Sequence[str]], np.ndarray]


def _similar(topics: Sequence[str], embed: Embed | None) -> np.ndarray:
    """Cosine similarity between every pair of topics. Without an embedder, exact matches only."""
    if embed is None:
        folded = [t.casefold() for t in topics]
        return np.array([[float(a == b) for b in folded] for a in folded])
    vecs = embed(list(topics)).astype(np.float64)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    vecs = vecs / np.where(norms == 0, 1.0, norms)
    return vecs @ vecs.T


def fresh_drafts(
    drafts: Sequence[LoopDraft],
    open_loops: Sequence[OpenLoop],
    embed: Embed | None,
    threshold: float,
) -> tuple[list[LoopDraft], list[str]]:
    """The drafts to add, and the ids of open loops that a timed draft replaces. `open_loops` must
    be the same user's. A draft that repeats an earlier draft of the same message is dropped."""
    if not drafts:
        return [], []
    topics = [loop.topic for loop in open_loops] + [d.topic for d in drafts]
    sim = _similar(topics, embed)
    n_open = len(open_loops)
    kept: list[LoopDraft] = []
    kept_rows: list[int] = []
    replaced: list[str] = []
    for i, draft in enumerate(drafts):
        row = n_open + i
        if any(sim[row, k] >= threshold for k in kept_rows):
            continue
        same = [loop.id for k, loop in enumerate(open_loops) if sim[row, k] >= threshold]
        if same and draft.event_at is None:
            continue
        replaced += [loop_id for loop_id in same if loop_id not in replaced]
        kept.append(draft)
        kept_rows.append(row)
    return kept, replaced
