"""Shared GPU model for the golden tests. Loaded once per pytest session, so the golden files do
not each fill VRAM with their own copy of the 4-bit model (Phase 5 sweep: up to 16 GB)."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def models():
    from hunch.llm.shared import borrowed

    if (held := borrowed()) is not None:  # the nightly job inside the bot lends its model
        return held
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("needs CUDA")
    from hunch.config import load_config
    from hunch.llm.model import ChatModel
    from hunch.memory.embeddings import QwenEmbedder

    e = load_config().embedding
    return ChatModel(), QwenEmbedder(e.model_id, e.device, e.query_instruction)
