"""The relevance gate's embedding threshold on a blind probe set (Berk, Phase 5; open since
Phase 3).

eval/probes/relevance_pairs.json was written by a separate agent that saw no code: 60 pairs of a
new message and an earlier memory of the same user, labelled relevant (recalling it would help
the reply) or not. A memory passes the gate if it shares a cue with the message OR its cosine
similarity to the message is at least `[recall] min_similarity` (0.45). This measures the
embedding half only (CPU, no LLM): the cue half needs the cue extraction and is more precise by
construction (a shared named cue).

Reported: precision and recall at the configured value, a sweep over thresholds, and every pair
the configured value gets wrong.

Usage:
    python -m scripts.relevance_probes          # cosine only (CPU)
    python -m scripts.relevance_probes --cues   # the full gate: + cue extraction (GPU)
Writes reports/phase5/relevance_probes.{json,md}.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from hunch.config import load_config

ROOT = Path(__file__).resolve().parents[1]
PROBES = ROOT / "eval" / "probes" / "relevance_pairs.json"
OUT = ROOT / "reports" / "phase5"
SWEEP = (0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60)


def scores(tp: int, fp: int, fn: int) -> tuple[float, float]:
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return precision, recall


def confusion(
    items: list[dict], sims: np.ndarray, threshold: float, shared: list[bool]
) -> tuple[int, int, int, int]:
    tp = fp = fn = tn = 0
    for it, s, cue in zip(items, sims, shared, strict=True):
        passed = cue or bool(s >= threshold)
        if passed and it["relevant"]:
            tp += 1
        elif passed:
            fp += 1
        elif it["relevant"]:
            fn += 1
        else:
            tn += 1
    return tp, fp, fn, tn


def shared_cues(items: list[dict]) -> list[bool]:
    """The cue half of the gate, as in the pipeline: message and memory share any cue. The
    memory's cues are extracted from its quoted message, as encoding does."""
    from datetime import date

    from hunch.llm.model import ChatModel
    from hunch.llm.types import SamplingSettings
    from hunch.recall.cues import extract_cues

    model = ChatModel()
    greedy = SamplingSettings(max_new_tokens=256, do_sample=False)

    def gen(messages: list[dict[str, str]]) -> str:
        return model.generate(messages, greedy).text

    today = date(2026, 10, 21)
    out = []
    for it in items:
        quote = it["memory"].removeprefix("They said: ").strip('"')
        a = extract_cues(it["message"], today, gen).cues
        b = extract_cues(quote, today, gen).cues
        out.append(bool(set(a) & set(b)))
    return out


def main() -> None:
    import sys

    from hunch.memory.embeddings import QwenEmbedder

    cfg = load_config()
    e = cfg.embedding
    embedder = QwenEmbedder(e.model_id, e.device, e.query_instruction)
    items = json.loads(PROBES.read_text(encoding="utf-8"))
    q = embedder.embed_queries([it["message"] for it in items])
    d = embedder.embed_documents([it["memory"] for it in items])
    sims = np.sum(q * d, axis=1)
    with_cues = "--cues" in sys.argv
    shared = shared_cues(items) if with_cues else [False] * len(items)

    configured = cfg.recall.min_similarity
    rows = []
    for t in sorted({*SWEEP, configured}):
        tp, fp, fn, tn = confusion(items, sims, t, shared)
        p, r = scores(tp, fp, fn)
        rows.append({"threshold": t, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                     "precision": round(p, 3), "recall": round(r, 3)})  # fmt: skip
    wrong = [
        {**it, "similarity": round(float(s), 3), "shared_cue": c}
        for it, s, c in zip(items, sims, shared, strict=True)
        if (c or bool(s >= configured)) is not it["relevant"]
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "relevance_probes.json").write_text(
        json.dumps(
            {"configured": configured, "with_cues": with_cues, "sweep": rows, "wrong": wrong,
             "shared_cue": shared,
             "similarities": [round(float(s), 3) for s in sims]},
            indent=2, ensure_ascii=False,
        ),
        encoding="utf-8",
    )  # fmt: skip
    rel = sims[[it["relevant"] for it in items]]
    irr = sims[[not it["relevant"] for it in items]]
    lines = [
        "# Relevance gate on the blind set"
        + (" (shared cue OR cosine)" if with_cues else " (cosine only)"),
        "",
        f"{len(items)} pairs ({len(rel)} relevant). Cosine: relevant median "
        f"{np.median(rel):.3f} (min {rel.min():.3f}), not relevant median {np.median(irr):.3f} "
        f"(max {irr.max():.3f}).",
        "",
        "| threshold | precision | recall | tp | fp | fn | tn |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        *(
            f"| {r['threshold']:.2f}{' (config)' if r['threshold'] == configured else ''} "
            f"| {r['precision']:.0%} | {r['recall']:.0%} | {r['tp']} | {r['fp']} | {r['fn']} "
            f"| {r['tn']} |"
            for r in rows
        ),
        "",
        f"## Wrong at {configured}",
        "",
        *(
            f"- {'missed' if w['relevant'] else 'let through'} ({w['similarity']}"
            f"{', shared cue' if w['shared_cue'] else ''}): "
            f"{w['message']!r} / {w['memory']!r}"
            for w in wrong
        ),
    ]
    (OUT / "relevance_probes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
