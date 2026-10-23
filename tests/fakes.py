"""Test doubles for the turn pipeline: a scripted chat model that records every prompt, and a
deterministic embedder. No GPU, no model download."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np

from hunch.llm.types import BatchGenerationResult, GenerationResult, SamplingSettings

CUE_PROMPT_START = "You extract memory cues"
JUDGE_PROMPT_START = "You review reply candidates"
SUMMARY_PROMPT_START = "You keep a running summary"
SECOND_OPINION_START = "You check one reply"
DISCLOSURE_START = "You guard the privacy"
SAME_MATTER_START = "You compare two short labels"


def _system(messages: list[dict[str, str]]) -> str:
    return messages[0]["content"] if messages and messages[0]["role"] == "system" else ""


@dataclass
class FakeLLM:
    """Answers each kind of call from a script; every prompt is kept in `prompts`."""

    candidates: Sequence[str] | Callable[[list[dict[str, str]]], Sequence[str]] = (
        "I'm sorry, that must be hard, tell me more?",
        "Nice! What happened next?",
        "Oh, how did it go?",
    )
    cues: list[dict] | Callable[[str], list[dict]] = field(default_factory=list)
    judge: Callable[[list[str]], str] | None = None  # candidate ids -> judge reply
    summary: str = "They talked about their week."
    second_opinion: str = "yes"  # the value is broken: keeps the judge's no (Phase 3 behaviour)
    disclosure: str | Callable[[str], str] = "no"  # disclosure judge (Phase 5): reply -> yes/no
    same_matter: str = "yes"  # loop topic judge (Phase 6)
    hit_cap: tuple[bool, ...] = ()
    prompts: list[list[dict[str, str]]] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)

    def _result(self, text: str) -> GenerationResult:
        return GenerationResult(text, 10, 5, 0.0, 0.0)

    def generate(
        self,
        messages: list[dict[str, str]],
        sampling: SamplingSettings | None = None,
        seed: int | None = None,
    ) -> GenerationResult:
        self.prompts.append(messages)
        system = _system(messages)
        if system.startswith(CUE_PROMPT_START):
            self.calls.append("cues")
            text = messages[-1]["content"]
            cues = self.cues(text) if callable(self.cues) else self.cues
            return self._result(json.dumps({"cues": cues}))
        if system.startswith(JUDGE_PROMPT_START):
            self.calls.append("judge")
            ids = [line[1] for line in messages[-1]["content"].splitlines() if line[:1] == "["]
            raw = self.judge(ids) if self.judge else "\n".join(f"{i} 8 ok" for i in ids)
            return self._result(raw)
        if system.startswith(SECOND_OPINION_START):
            self.calls.append("second_opinion")
            return self._result(self.second_opinion)
        if system.startswith(DISCLOSURE_START):
            self.calls.append("disclosure")
            reply = messages[-1]["content"].rsplit("Hunch's reply:\n", 1)[-1]
            verdict = self.disclosure(reply) if callable(self.disclosure) else self.disclosure
            return self._result(verdict)
        if system.startswith(SAME_MATTER_START):
            self.calls.append("same_matter")
            return self._result(self.same_matter)
        if system.startswith(SUMMARY_PROMPT_START):
            self.calls.append("summary")
            return self._result(self.summary)
        raise AssertionError(f"unexpected single generate call: {system[:60]!r}")

    def generate_batch(
        self,
        messages: list[dict[str, str]],
        n: int,
        sampling: SamplingSettings | None = None,
        seed: int | None = None,
    ) -> BatchGenerationResult:
        self.prompts.append(messages)
        self.calls.append("candidates")
        texts = tuple(self.candidates(messages) if callable(self.candidates) else self.candidates)
        assert len(texts) == n
        return BatchGenerationResult(
            texts, 100, tuple(20 for _ in texts), 0.0, 0.0, self.hit_cap or (False,) * n
        )

    def count_tokens(self, text: str) -> int:
        return len(text.split())

    @property
    def reasoning_prompts(self) -> list[list[dict[str, str]]]:
        return [p for p, c in zip(self.prompts, self.calls, strict=True) if c == "candidates"]


class HashEmbedder:
    """Bag-of-words vectors: texts sharing words are close; deterministic."""

    def __init__(self, dim: int = 16) -> None:
        self.dim = dim

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        for word in text.casefold().split():
            h = int(hashlib.md5(word.strip(".,!?\"'").encode()).hexdigest(), 16)
            v[h % self.dim] += 1.0
        n = np.linalg.norm(v)
        return v / n if n else v + 1 / np.sqrt(self.dim)

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray:
        return np.stack([self._vec(t) for t in texts])

    def embed_queries(self, texts: Sequence[str]) -> np.ndarray:
        return self.embed_documents(texts)
