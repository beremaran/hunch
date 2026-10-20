"""Text embeddings with Qwen3-Embedding-0.6B (CPU by default, to leave VRAM to the main model).

Follows the model card: left padding, last-token pooling, L2-normalised vectors. Queries get a
one-sentence English instruction; stored documents do not.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import numpy as np


class Embedder(Protocol):
    dim: int

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray: ...

    def embed_queries(self, texts: Sequence[str]) -> np.ndarray: ...


class QwenEmbedder:
    def __init__(
        self,
        model_id: str,
        device: str,
        query_instruction: str,
        max_length: int = 512,
    ) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        self._torch = torch
        self.device = device
        self.query_instruction = query_instruction
        self.max_length = max_length
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, padding_side="left")
        dtype = torch.float32 if device == "cpu" else torch.float16
        self.model = AutoModel.from_pretrained(model_id, dtype=dtype).to(device).eval()
        self.dim = int(self.model.config.hidden_size)

    def _embed(self, texts: Sequence[str]) -> np.ndarray:
        torch = self._torch
        batch = self.tokenizer(
            list(texts),
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        ).to(self.device)
        with torch.inference_mode():
            hidden = self.model(**batch).last_hidden_state
        pooled = hidden[:, -1]  # left padding: the last position is every sequence's last token
        pooled = torch.nn.functional.normalize(pooled.float(), p=2, dim=1)
        return pooled.cpu().numpy().astype(np.float32)

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray:
        return self._embed(texts)

    def embed_queries(self, texts: Sequence[str]) -> np.ndarray:
        return self._embed([f"Instruct: {self.query_instruction}\nQuery:{t}" for t in texts])
