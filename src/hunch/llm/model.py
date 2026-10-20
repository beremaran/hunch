"""Load the main model in 4-bit and generate chat replies with timing stats.

All GPU work stays behind this module so the model can be swapped later.
"""

from __future__ import annotations

import importlib
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import torch

from hunch.llm.types import BatchGenerationResult, GenerationResult, SamplingSettings

__all__ = [
    "BatchGenerationResult",
    "ChatModel",
    "GenerationResult",
    "LLMSettings",
    "SamplingSettings",
]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMSettings:
    model_id: str = "Qwen/Qwen3.5-9B"
    load_in_4bit: bool = True
    quant_type: str = "nf4"
    double_quant: bool = True
    compute_dtype: torch.dtype = torch.bfloat16
    device: str = "cuda:0"


@dataclass
class KernelStatus:
    """Which optional fast-kernel packages for the Gated DeltaNet layers import cleanly."""

    packages: dict[str, str] = field(default_factory=dict)  # name -> "ok" | error text
    fallback_warnings: list[str] = field(default_factory=list)

    @property
    def fast_path(self) -> bool:
        return all(v == "ok" for v in self.packages.values()) and not self.fallback_warnings


_KERNEL_IMPORTS = {
    "fla.chunk_gated_delta_rule": ("fla.ops.gated_delta_rule", "chunk_gated_delta_rule"),
    "fla.fused_recurrent_gated_delta_rule": (
        "fla.ops.gated_delta_rule",
        "fused_recurrent_gated_delta_rule",
    ),
    "causal_conv1d.causal_conv1d_fn": ("causal_conv1d", "causal_conv1d_fn"),
    "causal_conv1d.causal_conv1d_update": ("causal_conv1d", "causal_conv1d_update"),
}


def probe_kernel_packages() -> dict[str, str]:
    out: dict[str, str] = {}
    for name, (module, attr) in _KERNEL_IMPORTS.items():
        try:
            getattr(importlib.import_module(module), attr)
            out[name] = "ok"
        except Exception as exc:  # report any import failure, not just ImportError
            out[name] = f"{type(exc).__name__}: {exc}"[:200]
    return out


class _FallbackCapture(logging.Handler):
    """Collects transformers' 'falling back to its reference PyTorch implementation' warnings."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        if "falling back" in msg.lower() or "fast path" in msg.lower():
            self.messages.append(msg)


class _FirstTokenTimer:
    """StoppingCriteria-compatible callable that timestamps the first generated token."""

    def __init__(self) -> None:
        self.first_token_at: float | None = None

    def __call__(
        self, input_ids: torch.Tensor, scores: torch.Tensor, **kwargs: Any
    ) -> torch.Tensor:
        if self.first_token_at is None:
            torch.cuda.synchronize()
            self.first_token_at = time.perf_counter()
        return torch.zeros(input_ids.shape[0], dtype=torch.bool, device=input_ids.device)


class ChatModel:
    def __init__(self, settings: LLMSettings | None = None) -> None:
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        self.settings = settings or LLMSettings()
        s = self.settings
        self._fallback = _FallbackCapture()
        logging.getLogger("transformers").addHandler(self._fallback)

        quant = None
        if s.load_in_4bit:
            quant = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type=s.quant_type,
                bnb_4bit_use_double_quant=s.double_quant,
                bnb_4bit_compute_dtype=s.compute_dtype,
            )
        self.tokenizer = AutoTokenizer.from_pretrained(s.model_id)
        self.model = AutoModelForCausalLM.from_pretrained(
            s.model_id,
            quantization_config=quant,
            dtype=s.compute_dtype,
            device_map={"": s.device},
        )
        self.model.eval()

    def kernel_status(self) -> KernelStatus:
        return KernelStatus(probe_kernel_packages(), list(dict.fromkeys(self._fallback.messages)))

    def render(self, messages: list[dict[str, str]], enable_thinking: bool = False) -> str:
        return self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True, enable_thinking=enable_thinking
        )

    def generate(
        self,
        messages: list[dict[str, str]],
        sampling: SamplingSettings | None = None,
        seed: int | None = None,
    ) -> GenerationResult:
        b = self.generate_batch(messages, 1, sampling, seed)
        return GenerationResult(
            text=b.texts[0],
            prompt_tokens=b.prompt_tokens,
            new_tokens=b.new_tokens[0],
            prefill_s=b.prefill_s,
            total_s=b.total_s,
        )

    @torch.inference_mode()
    def generate_batch(
        self,
        messages: list[dict[str, str]],
        n: int,
        sampling: SamplingSettings | None = None,
        seed: int | None = None,
    ) -> BatchGenerationResult:
        """n sampled replies to the same prompt in one batched call (reply candidates)."""
        from transformers import StoppingCriteriaList

        sp = sampling or SamplingSettings()
        prompt = self.render(messages, enable_thinking=sp.enable_thinking)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.settings.device)
        n_prompt = int(inputs["input_ids"].shape[1])
        if seed is not None:
            torch.manual_seed(seed)

        timer = _FirstTokenTimer()
        torch.cuda.synchronize()
        start = time.perf_counter()
        out = self.model.generate(
            **inputs,
            num_return_sequences=n,
            max_new_tokens=sp.max_new_tokens,
            min_new_tokens=sp.min_new_tokens or None,
            do_sample=sp.do_sample,
            temperature=sp.temperature if sp.do_sample else None,
            top_p=sp.top_p if sp.do_sample else None,
            top_k=sp.top_k if sp.do_sample else None,
            stopping_criteria=StoppingCriteriaList([timer]),
            pad_token_id=self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
        )
        torch.cuda.synchronize()
        end = time.perf_counter()

        stop_ids = self._stop_token_ids()
        texts, lengths, capped = [], [], []
        for row in out[:, n_prompt:]:
            ids = row.tolist()
            stop = next((i + 1 for i, t in enumerate(ids) if t in stop_ids), None)
            length = stop or len(ids)
            lengths.append(length)
            capped.append(stop is None)
            texts.append(self.tokenizer.decode(ids[:length], skip_special_tokens=True).strip())
        first = timer.first_token_at or end
        return BatchGenerationResult(
            texts=tuple(texts),
            prompt_tokens=n_prompt,
            new_tokens=tuple(lengths),
            prefill_s=first - start,
            total_s=end - start,
            hit_cap=tuple(capped),
        )

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer(text, add_special_tokens=False)["input_ids"])

    def reset_peak_memory(self) -> None:
        torch.cuda.reset_peak_memory_stats(self.settings.device)

    def peak_memory_gib(self) -> float:
        return torch.cuda.max_memory_allocated(self.settings.device) / 2**30

    def _stop_token_ids(self) -> set[int]:
        eos = self.model.generation_config.eos_token_id
        ids = set(eos if isinstance(eos, list) else [eos]) if eos is not None else set()
        if self.tokenizer.eos_token_id is not None:
            ids.add(self.tokenizer.eos_token_id)
        if self.tokenizer.pad_token_id is not None:
            ids.add(self.tokenizer.pad_token_id)
        return ids
