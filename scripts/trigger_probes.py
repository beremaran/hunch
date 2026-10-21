"""The "asks why" detector on its blind set (Phase 4), measured once after it was frozen.

eval/probes/asks_why.json was written by a separate agent that saw no code: 30 messages asking
Hunch why it said what it said, 30 hard negatives ("why is my cat so weird", "why not").

Usage:
    python -m scripts.trigger_probes   # writes reports/phase4/asks_why_probe.{json,md}
"""

from __future__ import annotations

import json
from pathlib import Path

from hunch.reflection.triggers import asks_why

ROOT = Path(__file__).resolve().parents[1]
PROBES = ROOT / "eval" / "probes" / "asks_why.json"
OUT = ROOT / "reports" / "phase4"


def main() -> None:
    items = json.loads(PROBES.read_text(encoding="utf-8"))
    rows = [{"text": it["text"], "label": it["asks_why"], "got": asks_why(it["text"])}
            for it in items]  # fmt: skip
    tp = sum(r["label"] and r["got"] for r in rows)
    fp = sum(not r["label"] and r["got"] for r in rows)
    fn = sum(r["label"] and not r["got"] for r in rows)
    pos, neg = sum(r["label"] for r in rows), sum(not r["label"] for r in rows)
    summary = {
        "positives": pos, "negatives": neg, "tp": tp, "fp": fp, "fn": fn,
        "precision": round(tp / (tp + fp), 3) if tp + fp else None,
        "recall": round(tp / pos, 3) if pos else None,
        "missed": [r["text"] for r in rows if r["label"] and not r["got"]],
        "false_positives": [r["text"] for r in rows if not r["label"] and r["got"]],
    }  # fmt: skip
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "asks_why_probe.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md = [
        '# "Asks why" detector on the blind set',
        "",
        f"{pos} positives, {neg} negatives. Precision {summary['precision']}, "
        f"recall {summary['recall']} (TP {tp}, FP {fp}, FN {fn}).",
        "",
        "Missed:",
        *[f"- {t}" for t in summary["missed"]],
        "",
        "False positives:",
        *[f"- {t}" for t in summary["false_positives"]],
    ]
    (OUT / "asks_why_probe.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
