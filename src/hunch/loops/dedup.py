"""One open loop per matter (Berk, Phase 6). The model labels the same matter differently each
time the user mentions it ("contract", "getting the new contract"), so a new draft is compared
with the user's open loops by topic embedding. A match is dropped, unless the new draft names a
clock time: then the user gave a (new) date for it, and the draft replaces the old loops.

Embeddings put "flight to Berlin" and "flight to Madrid" close together, so two topics that both
name someone or somewhere, with no name in common, are never the same matter (Berk, Phase 6).
They also put "renting a flat" and "buying a flat" close together, so a pair at or above the
threshold goes to a short model judge (Berk, Phase 6); only its "yes" merges."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence

import numpy as np

from hunch.loops.extract import LoopDraft
from hunch.loops.store import OpenLoop

Embed = Callable[[Sequence[str]], np.ndarray]
Generate = Callable[[list[dict[str, str]]], str]

SAME_MATTER_PROMPT = """You compare two short labels of things a user said they will do or are
waiting for. Are both labels about the same single matter, so that asking about one would also
answer the other? Different people, places, items, body parts, subjects or actions (renting vs
buying, buying vs repairing) are different matters. Answer with exactly one word: yes or no."""
SAME_MATTER_MAX_NEW_TOKENS = 4


_WORD = re.compile(r"[^\W\d_][\w-]*(?:['’]s)?")


def _words(topic: str) -> list[str]:
    return [re.sub(r"['’]s$", "", w) for w in _WORD.findall(topic)]


def names(topic: str) -> frozenset[str]:
    """The capitalised words of a topic, casefolded. A first word capitalised as at the start of a
    sentence ("Dinner with Tom") counts too; `distinct_names` lets the other topic undo it."""
    return frozenset(w.casefold() for w in _words(topic) if w[0].isupper() and w != "I")


def distinct_names(a: str, b: str) -> bool:
    """Both topics name someone or somewhere, and no name is shared. A capitalised word that the
    other topic has in lower case ("Dinner" / "dinner") is not a name."""
    na, nb = names(a), names(b)
    if na & nb:
        return False
    na -= {w.casefold() for w in _words(b)}
    nb -= {w.casefold() for w in _words(a)}
    return bool(na) and bool(nb)


def build_same_matter_messages(a: str, b: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SAME_MATTER_PROMPT},
        {"role": "user", "content": f"Label 1: {a}\nLabel 2: {b}"},
    ]


def parse_same_matter(raw: str) -> bool:
    """Only a clear "yes" merges: a lost loop costs more than a repeated question."""
    return re.match(r"\W*yes\b", raw.casefold()) is not None


def judged_same(generate: Generate) -> Callable[[str, str], bool]:
    """A judge that asks the model once per pair of topics."""
    seen: dict[tuple[str, str], bool] = {}

    def same(a: str, b: str) -> bool:
        if (a, b) not in seen:
            seen[(a, b)] = parse_same_matter(generate(build_same_matter_messages(a, b)))
        return seen[(a, b)]

    return same


def _similar(topics: Sequence[str], embed: Embed | None) -> np.ndarray:
    """Cosine similarity between every pair of topics. Without an embedder, exact matches only."""
    if embed is None:
        folded = [t.casefold() for t in topics]
        return np.array([[float(a == b) for b in folded] for a in folded])
    vecs = embed(list(topics)).astype(np.float64)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    vecs = vecs / np.where(norms == 0, 1.0, norms)
    sim = vecs @ vecs.T
    for i, a in enumerate(topics):
        for j, b in enumerate(topics):
            if i != j and distinct_names(a, b):
                sim[i, j] = 0.0
    return sim


def fresh_drafts(
    drafts: Sequence[LoopDraft],
    open_loops: Sequence[OpenLoop],
    embed: Embed | None,
    threshold: float,
    same: Callable[[str, str], bool] | None = None,
) -> tuple[list[LoopDraft], list[str]]:
    """The drafts to add, and the ids of open loops that a timed draft replaces. `open_loops` must
    be the same user's. A draft that repeats an earlier draft of the same message is dropped.
    With `same`, a pair at or above the threshold merges only when the judge says so."""
    if not drafts:
        return [], []
    topics = [loop.topic for loop in open_loops] + [d.topic for d in drafts]
    sim = _similar(topics, embed)
    if same is not None:
        for i, j in zip(*np.nonzero(sim >= threshold), strict=True):
            if i >= j or j < len(open_loops) or topics[i].casefold() == topics[j].casefold():
                continue  # judge only a new draft, and never two identical topics
            if not same(topics[i], topics[j]):
                sim[i, j] = sim[j, i] = 0.0
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
