"""Generation settings, results and the model interface the pipeline depends on (no torch here,
so the pipeline can be tested with a fake model)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SamplingSettings:
    """Defaults follow Qwen's recommendation for non-thinking general chat.

    Qwen also recommends presence_penalty=1.5, which transformers' generate() does not offer.
    """

    max_new_tokens: int = 384
    min_new_tokens: int = 0
    temperature: float = 0.7
    top_p: float = 0.8
    top_k: int = 20
    do_sample: bool = True
    enable_thinking: bool = False


GREEDY = SamplingSettings(max_new_tokens=256, do_sample=False)


@dataclass(frozen=True)
class GenerationResult:
    text: str
    prompt_tokens: int
    new_tokens: int
    prefill_s: float  # time to first new token (prefill + one decode step)
    total_s: float

    @property
    def decode_tok_per_s(self) -> float:
        decode_s = self.total_s - self.prefill_s
        return (self.new_tokens - 1) / decode_s if self.new_tokens > 1 and decode_s > 0 else 0.0

    @property
    def prefill_tok_per_s(self) -> float:
        return self.prompt_tokens / self.prefill_s if self.prefill_s > 0 else 0.0


@dataclass(frozen=True)
class BatchGenerationResult:
    texts: tuple[str, ...]
    prompt_tokens: int
    new_tokens: tuple[int, ...]  # per sequence, up to and including the stop token
    prefill_s: float
    total_s: float
    hit_cap: tuple[bool, ...] = ()  # per sequence: stopped by max_new_tokens, not a stop token

    @property
    def decode_steps_per_s(self) -> float:
        """Tokens per second each sequence gets (the batch advances one step for all)."""
        decode_s = self.total_s - self.prefill_s
        steps = max(self.new_tokens) - 1
        return steps / decode_s if steps > 0 and decode_s > 0 else 0.0

    @property
    def aggregate_tok_per_s(self) -> float:
        decode_s = self.total_s - self.prefill_s
        toks = sum(t - 1 for t in self.new_tokens)
        return toks / decode_s if toks > 0 and decode_s > 0 else 0.0


class ChatLLM(Protocol):
    """What the turn pipeline needs from the main model (hunch.llm.model.ChatModel)."""

    def generate(
        self,
        messages: list[dict[str, str]],
        sampling: SamplingSettings | None = None,
        seed: int | None = None,
    ) -> GenerationResult: ...

    def generate_batch(
        self,
        messages: list[dict[str, str]],
        n: int,
        sampling: SamplingSettings | None = None,
        seed: int | None = None,
    ) -> BatchGenerationResult: ...

    def count_tokens(self, text: str) -> int: ...
