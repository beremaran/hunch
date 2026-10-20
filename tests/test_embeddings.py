"""Real Qwen3-Embedding-0.6B on CPU. Needs the downloaded model: `pytest -m slow`."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from hunch.config import load_config

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def embedder():
    from hunch.memory.embeddings import QwenEmbedder

    cfg = load_config().embedding
    return QwenEmbedder(cfg.model_id, cfg.device, cfg.query_instruction)


def test_shape_and_normalisation(embedder) -> None:
    vecs = embedder.embed_documents(["My sister moved to Lisbon.", "We danced to Hallelujah."])
    assert vecs.shape == (2, load_config().embedding.dim)
    assert np.allclose(np.linalg.norm(vecs, axis=1), 1.0, atol=1e-4)


def test_related_memory_ranks_first(embedder) -> None:
    docs = embedder.embed_documents(
        [
            "Anna said her sister is moving to Lisbon next month.",
            "Ben's landlord still hasn't fixed the heating.",
            "Anna and Tom danced to Hallelujah at their wedding.",
        ]
    )
    query = embedder.embed_queries(["How is your sister settling in after the move?"])[0]
    scores = docs @ query
    assert int(np.argmax(scores)) == 0


def test_store_round_trip_with_real_embeddings(embedder, tmp_path: Path) -> None:
    from hunch.memory.schema import Memory
    from hunch.memory.store import MemoryStore

    store = MemoryStore(tmp_path / "h.db", core_dir=tmp_path / "core", embedding_dim=embedder.dim)
    texts = ["The heating in Ben's flat is broken.", "Anna loves the song Hallelujah."]
    for i, (text, vec) in enumerate(zip(texts, embedder.embed_documents(texts), strict=True)):
        ep = store.append_turn("c1", "u_anna", "user", text)
        store.add_memory(
            Memory(f"m{i}", "u_anna", "general", ep.id, text, {}, (0.0, 0.5), 0.5, 0.0), vec
        )
    [(hit, _)] = store.similar(embedder.embed_queries(["Is it still cold at Ben's?"])[0], k=1)
    assert hit.id == "m0"
    store.close()
