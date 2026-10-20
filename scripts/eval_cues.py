"""Precision and recall of LLM cue extraction on the hand-labelled set (eval/cues/labelled.json).

The labels were written blind, without seeing the extraction prompt. Matching is exact on the
normalised "type:value" key; a second, lenient score also counts a cue as found when the type
matches and one value contains the other (e.g. "lake_como" vs "como").

Sets, all labelled blind by a separate agent: "labelled" is the tuning set the prompt was
improved on; "heldout" was measured once at the end of Phase 2; "heldout2" is measured once after
the rule-based date finder was frozen (Phase 3). By default date cues come from the LLM plus the
rule-based finder; --no-rule-dates measures the LLM alone.

Usage:
    python scripts/eval_cues.py --set labelled   # reports/phase2/cue_extraction-labelled.*
    python scripts/eval_cues.py --set heldout    # reports/phase2/cue_extraction-heldout.*
    python scripts/eval_cues.py --set heldout2   # reports/phase3/cue_extraction-heldout2.*
    python scripts/eval_cues.py --set heldout2 --no-rule-dates  # ...-heldout2-llm-only.*
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

from hunch.memory.schema import CUE_TYPES
from hunch.recall.cues import extract_cues, llm_generate, normalize_value

ROOT = Path(__file__).resolve().parents[1]
CUE_SETS = ROOT / "eval" / "cues"
REPORTS = ROOT / "reports"
OUT_DIRS = {"labelled": "phase2", "heldout": "phase2", "heldout2": "phase3"}


def _norm_key(key: str) -> str:
    kind, _, value = key.partition(":")
    return f"{kind}:{value if kind == 'date' else normalize_value(value)}"


def lenient_match(a: str, b: str) -> bool:
    ka, _, va = a.partition(":")
    kb, _, vb = b.partition(":")
    return ka == kb and (va in vb or vb in va)


def score(gold: list[set[str]], pred: list[set[str]], lenient: bool = False) -> dict:
    per_type: dict[str, dict[str, int]] = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    for g, p in zip(gold, pred, strict=True):
        matched_g: set[str] = set()
        for cue in p:
            kind = cue.partition(":")[0]
            hit = next(
                (x for x in g - matched_g if (lenient_match(cue, x) if lenient else cue == x)),
                None,
            )
            if hit:
                matched_g.add(hit)
                per_type[kind]["tp"] += 1
            else:
                per_type[kind]["fp"] += 1
        for cue in g - matched_g:
            per_type[cue.partition(":")[0]]["fn"] += 1

    def pr(c: dict[str, int]) -> dict:
        p = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else None
        r = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else None
        return {**c, "precision": p, "recall": r}

    total = {k: sum(c[k] for c in per_type.values()) for k in ("tp", "fp", "fn")}
    return {"overall": pr(total), "per_type": {t: pr(per_type[t]) for t in CUE_TYPES}}


def fmt(x: float | None) -> str:
    return "-" if x is None else f"{x:.0%}"


def main() -> None:
    from hunch.llm.model import ChatModel

    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=tuple(OUT_DIRS), required=True)
    ap.add_argument(
        "--no-rule-dates", action="store_true", help="date cues from the LLM alone, no rules"
    )
    args = ap.parse_args()
    out_dir = REPORTS / OUT_DIRS[args.set]
    name = f"cue_extraction-{args.set}{'-llm-only' if args.no_rule_dates else ''}"
    data = json.loads((CUE_SETS / f"{args.set}.json").read_text(encoding="utf-8"))
    today = date.fromisoformat(data["today"])
    model = ChatModel()
    generate = llm_generate(model)
    rows = []
    for it in data["items"]:
        t0 = time.perf_counter()
        out = extract_cues(it["text"], today, generate, rule_dates=not args.no_rule_dates)
        rows.append(
            {
                "id": it["id"],
                "text": it["text"],
                "gold": sorted(_norm_key(c) for c in it["cues"]),
                "pred": sorted(out.cues),
                "strengths": out.cues,
                "rule_dates": list(out.rule_dates),
                "dropped": list(out.dropped),
                "attempts": out.attempts,
                "errors": list(out.errors),
                "latency_s": round(time.perf_counter() - t0, 2),
            }
        )
        print(f"{it['id']}: gold={rows[-1]['gold']} pred={rows[-1]['pred']}", flush=True)

    gold = [set(r["gold"]) for r in rows]
    pred = [set(r["pred"]) for r in rows]
    strict, lenient = score(gold, pred), score(gold, pred, lenient=True)
    lat = sorted(r["latency_s"] for r in rows)
    report = {
        "n_messages": len(rows),
        "rule_dates": not args.no_rule_dates,
        "strict": strict,
        "lenient": lenient,
        "latency_s": {"median": lat[len(lat) // 2], "max": lat[-1]},
        "retries": sum(r["attempts"] > 1 for r in rows),
        "failed": sum(not r["pred"] and r["errors"] != [] for r in rows),
        "rows": rows,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{name}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    lines = [
        "| type | gold | strict P | strict R | lenient P | lenient R |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for t in (*CUE_TYPES, "overall"):
        s = strict["overall"] if t == "overall" else strict["per_type"][t]
        le = lenient["overall"] if t == "overall" else lenient["per_type"][t]
        lines.append(
            f"| {t} | {s['tp'] + s['fn']} | {fmt(s['precision'])} | {fmt(s['recall'])} "
            f"| {fmt(le['precision'])} | {fmt(le['recall'])} |"
        )
    lat_s = report["latency_s"]
    lines += [
        "",
        f"Latency per message: median {lat_s['median']} s, max {lat_s['max']} s; "
        f"retries: {report['retries']}",
        "",
        "Errors:",
    ]
    for r in rows:
        fp = sorted(set(r["pred"]) - set(r["gold"]))
        fn = sorted(set(r["gold"]) - set(r["pred"]))
        if fp or fn:
            lines.append(f"- {r['id']} {r['text'][:70]!r}: extra {fp}, missed {fn}")
    (out_dir / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
