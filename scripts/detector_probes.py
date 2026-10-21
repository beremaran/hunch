"""Phase 5 rule-based detectors on their blind probe sets, measured once (Berk: blind sets are
written by an agent that saw no code; the detectors were written by another agent that never saw
the sets). CPU only.

- sensitive categories (eval/probes/sensitive_categories.json): keywords alone, embedding
  prototypes alone at a sweep of thresholds, and keywords OR embedding (the detector); per item a
  category set, scored per (item, category) pair;
- privacy answers (privacy_answers.json): private / general / unclear;
- forget requests (forget_requests.json): request yes/no, scope, topic;
- hostility and apology (hostility.json): hostile / apology / neither.

Usage:
    python -m scripts.detector_probes   # writes reports/phase5/detector_probes.{json,md}
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBES = ROOT / "eval" / "probes"
OUT = ROOT / "reports" / "phase5"
SWEEP = (0.45, 0.50, 0.55, 0.60, 0.65, 0.70)


def _load(name: str) -> list[dict]:
    return json.loads((PROBES / name).read_text(encoding="utf-8"))


def _pr(tp: int, fp: int, fn: int) -> str:
    p = tp / (tp + fp) if tp + fp else 1.0
    r = tp / (tp + fn) if tp + fn else 1.0
    return f"precision {p:.0%} ({tp}/{tp + fp}), recall {r:.0%} ({tp}/{tp + fn})"


def _pairs(gold: list[set[str]], pred: list[set[str]]) -> tuple[int, int, int]:
    tp = sum(len(g & p) for g, p in zip(gold, pred, strict=True))
    fp = sum(len(p - g) for g, p in zip(gold, pred, strict=True))
    fn = sum(len(g - p) for g, p in zip(gold, pred, strict=True))
    return tp, fp, fn


def categories(lines: list[str], out: dict) -> None:
    import numpy as np

    from hunch.config import load_config
    from hunch.memory.embeddings import QwenEmbedder
    from hunch.privacy.categories import CategoryDetector, keyword_categories

    cfg = load_config()
    e = cfg.embedding
    cats = cfg.privacy.categories
    items = _load("sensitive_categories.json")
    gold = [set(it["categories"]) for it in items]
    embedder = QwenEmbedder(e.model_id, e.device, e.query_instruction)
    det = CategoryDetector(cats, embedder, cfg.privacy.prototype_min_similarity)
    q = embedder.embed_queries([it["text"] for it in items])
    sims = [det.similarities(np.asarray(v)) for v in q]
    kw = [set(keyword_categories(it["text"], cats)) for it in items]
    lines += ["## Sensitive categories", "", f"{len(items)} messages, scored per category.", ""]
    lines.append(f"- keywords alone: {_pr(*_pairs(gold, kw))}")
    rows = []
    for t in SWEEP:
        emb = [{c for c, s in sim.items() if s >= t} for sim in sims]
        both = [k | m for k, m in zip(kw, emb, strict=True)]
        rows.append({"threshold": t, "embedding": _pairs(gold, emb), "both": _pairs(gold, both)})
        mark = " (config)" if t == cfg.privacy.prototype_min_similarity else ""
        lines.append(
            f"- {t:.2f}{mark}: embedding alone {_pr(*_pairs(gold, emb))}; keywords OR embedding "
            f"{_pr(*_pairs(gold, both))}"
        )
    # Message level: any sensitive category vs none (what decides private vs general).
    lines.append("")
    for t in SWEEP:
        pred = [
            bool(k) or any(s >= t for s in sim.values()) for k, sim in zip(kw, sims, strict=True)
        ]
        g = [bool(x) for x in gold]
        tp = sum(a and b for a, b in zip(g, pred, strict=True))
        fp = sum(b and not a for a, b in zip(g, pred, strict=True))
        fn = sum(a and not b for a, b in zip(g, pred, strict=True))
        lines.append(f"- message is sensitive at {t:.2f}: {_pr(tp, fp, fn)}")
    out["categories"] = {
        "sweep": rows,
        "items": [
            {"text": it["text"], "gold": sorted(g), "keywords": sorted(k),
             "similarities": {c: round(s, 3) for c, s in sim.items()}}
            for it, g, k, sim in zip(items, gold, kw, sims, strict=True)
        ],
    }  # fmt: skip
    lines.append("")


def answers(lines: list[str], out: dict) -> None:
    from hunch.privacy.answers import parse_privacy_answer

    items = _load("privacy_answers.json")
    pred = [parse_privacy_answer(it["text"]) or "unclear" for it in items]
    conf = Counter((it["answer"], p) for it, p in zip(items, pred, strict=True))
    ok = sum(it["answer"] == p for it, p in zip(items, pred, strict=True))
    lines += ["## Privacy answers", "", f"{ok}/{len(items)} correct. (gold, predicted): "
              + ", ".join(f"{k}: {v}" for k, v in sorted(conf.items())), ""]  # fmt: skip
    dangerous = [it["text"] for it, p in zip(items, pred, strict=True)
                 if p == "general" and it["answer"] != "general"]  # fmt: skip
    lines += [f"Read as general but not general (would make a memory tellable): {len(dangerous)}",
              *(f"- {t!r}" for t in dangerous), ""]  # fmt: skip
    out["answers"] = [
        {**it, "predicted": p} for it, p in zip(items, pred, strict=True) if it["answer"] != p
    ]


def forget(lines: list[str], out: dict) -> None:
    from hunch.memory.forget_requests import detect_forget_request

    items = _load("forget_requests.json")
    preds = [detect_forget_request(it["text"]) for it in items]
    tp = sum(bool(p) and it["forget"] for it, p in zip(items, preds, strict=True))
    fp = sum(bool(p) and not it["forget"] for it, p in zip(items, preds, strict=True))
    fn = sum(not p and it["forget"] for it, p in zip(items, preds, strict=True))
    scope = sum(
        bool(p) and it["forget"] and p.scope == it["scope"]
        for it, p in zip(items, preds, strict=True)
    )
    lines += ["## Forget requests", "", f"- request: {_pr(tp, fp, fn)}",
              f"- scope right among caught requests: {scope}/{tp}", ""]  # fmt: skip
    out["forget"] = [
        {**it, "predicted": None if p is None else {"scope": p.scope, "topic": p.topic}}
        for it, p in zip(items, preds, strict=True)
        if bool(p) != it["forget"] or (p and (p.scope != it["scope"] or p.topic != it["topic"]))
    ]


def hostility(lines: list[str], out: dict) -> None:
    from hunch.mood.signals import is_apology, is_hostile

    items = _load("hostility.json")
    pred = [
        "hostile" if is_hostile(it["text"]) else "apology" if is_apology(it["text"]) else "neither"
        for it in items
    ]
    lines += ["## Hostility and apology", ""]
    for label in ("hostile", "apology"):
        tp = sum(it["label"] == label and p == label for it, p in zip(items, pred, strict=True))
        fp = sum(it["label"] != label and p == label for it, p in zip(items, pred, strict=True))
        fn = sum(it["label"] == label and p != label for it, p in zip(items, pred, strict=True))
        lines.append(f"- {label}: {_pr(tp, fp, fn)}")
    lines.append("")
    out["hostility"] = [
        {**it, "predicted": p} for it, p in zip(items, pred, strict=True) if it["label"] != p
    ]


def main() -> None:
    lines = ["# Phase 5 detectors on their blind sets (measured once)", ""]
    out: dict = {}
    answers(lines, out)
    forget(lines, out)
    hostility(lines, out)
    categories(lines, out)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "detector_probes.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (OUT / "detector_probes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
