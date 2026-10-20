"""Benchmark the main model: load time, VRAM, prefill and decode speed, kernel fast path.

Usage:
    python scripts/bench_llm.py --tag torch-fallback
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import time
from pathlib import Path

import torch

from hunch.llm.model import ChatModel, LLMSettings, SamplingSettings

OUT_DIR = Path(__file__).resolve().parents[1] / "eval" / "results"

SHORT = [
    {"role": "user", "content": "Erzähl mir eine kurze Geschichte über einen alten Leuchtturm."}
]
FILLER = (
    "Bu hafta çok yoğundu. Pazartesi işte uzun bir toplantı vardı, salı günü annemi ziyaret ettim, "
    "çarşamba spor salonuna gittim ve perşembe arkadaşlarla yemeğe çıktık. "
)
LONG = [{"role": "user", "content": FILLER * 60 + "\nBütün bunları iki cümleyle özetler misin?"}]


def nvidia_smi_used_mib() -> int | None:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return int(out.strip().splitlines()[0])
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None


def run_case(model: ChatModel, name: str, messages: list, n_new: int, repeats: int) -> dict:
    sp = SamplingSettings(max_new_tokens=n_new, min_new_tokens=n_new, do_sample=False)
    torch.cuda.reset_peak_memory_stats()
    runs = [model.generate(messages, sp) for _ in range(repeats)]
    best = max(runs, key=lambda r: r.decode_tok_per_s)
    return {
        "case": name,
        "prompt_tokens": best.prompt_tokens,
        "new_tokens": best.new_tokens,
        "prefill_s": round(best.prefill_s, 3),
        "prefill_tok_per_s": round(best.prefill_tok_per_s, 1),
        "decode_tok_per_s": round(best.decode_tok_per_s, 2),
        "decode_tok_per_s_all": [round(r.decode_tok_per_s, 2) for r in runs],
        "total_s": round(best.total_s, 2),
        "peak_allocated_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
        "peak_reserved_gib": round(torch.cuda.max_memory_reserved() / 2**30, 2),
        "sample_text": best.text[:300],
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="label for this configuration")
    ap.add_argument("--repeats", type=int, default=2)
    args = ap.parse_args()

    smi_before = nvidia_smi_used_mib()
    t0 = time.perf_counter()
    model = ChatModel(LLMSettings())
    load_s = time.perf_counter() - t0
    after_load_gib = torch.cuda.memory_allocated() / 2**30
    footprint_gib = model.model.get_memory_footprint() / 2**30

    model.generate(SHORT, SamplingSettings(max_new_tokens=8, do_sample=False))  # warm-up
    cases = [
        run_case(model, "short_prompt_256_new", SHORT, 256, args.repeats),
        run_case(model, "long_prompt_128_new", LONG, 128, args.repeats),
    ]
    status = model.kernel_status()

    report = {
        "tag": args.tag,
        "model_id": model.settings.model_id,
        "quant": "bnb-4bit nf4 double-quant, bf16 compute",
        "platform": platform.platform(),
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0),
        "load_s": round(load_s, 1),
        "weights_allocated_gib": round(after_load_gib, 2),
        "model_footprint_gib": round(footprint_gib, 2),
        "nvidia_smi_used_mib_before": smi_before,
        "nvidia_smi_used_mib_after": nvidia_smi_used_mib(),
        "kernels": status.packages,
        "fallback_warnings": status.fallback_warnings,
        "fast_path": status.fast_path,
        "cases": cases,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"bench-{args.tag}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2))
    for c in cases:
        print({k: v for k, v in c.items() if k != "sample_text"})
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
