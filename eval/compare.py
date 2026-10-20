"""Diff two eval runs: flag rates per language and per-prompt clean rates.

Both runs are re-checked with the current scoring and the current item definitions, so the
comparison is apples to apples. Items that exist in only one run are listed separately.

Usage:
    python -m eval.compare phase0-baseline phase1
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

from eval.run_eval import EVAL_DIR, SUMMARY_FLAGS, has_flag
from eval.scoring import REPLY_LANG, check_reply


def load_rows(tag: str, items: dict[str, dict]) -> list[dict]:
    path = EVAL_DIR / "results" / tag / "outputs.jsonl"
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        r = json.loads(line)
        if r["id"] in items:
            r["checks"] = check_reply(items[r["id"]], r["reply"]).to_dict()
            rows.append(r)
    return rows


def rate(rows: list[dict], flag: str | None) -> float:
    if not rows:
        return float("nan")
    hits = sum((not r["checks"]["flags"]) if flag is None else has_flag(r, flag) for r in rows)
    return hits / len(rows)


def compare(old_tag: str, new_tag: str) -> str:
    data = json.loads((EVAL_DIR / "prompts.json").read_text(encoding="utf-8"))
    # Expected-fail prompts (known issues) are left out of the diff.
    items = {it["id"]: it for it in data["items"] if not it.get("expected_fail")}
    old, new = load_rows(old_tag, items), load_rows(new_tag, items)
    common = {r["id"] for r in old} & {r["id"] for r in new}
    old_c = [r for r in old if r["id"] in common]
    new_c = [r for r in new if r["id"] in common]

    lines = [
        f"# Eval diff: {old_tag} -> {new_tag}",
        "",
        f"Common prompts: {len(common)}. Only in {old_tag}: "
        f"{len({r['id'] for r in old} - common)}. Only in {new_tag}: "
        f"{len({r['id'] for r in new} - common)}. Rates are per sampled reply.",
        "",
        "| lang | metric | " + old_tag + " | " + new_tag + " | delta |",
        "| --- | --- | --- | --- | --- |",
    ]
    for lang in (REPLY_LANG,):
        o = [r for r in old_c if r["lang"] == lang]
        n = [r for r in new_c if r["lang"] == lang]
        if not o or not n:
            continue
        for metric in (None, *SUMMARY_FLAGS):
            ro, rn = rate(o, metric), rate(n, metric)
            if metric is not None and ro == 0 and rn == 0:
                continue
            name = "clean" if metric is None else metric
            lines.append(f"| {lang} | {name} | {ro:.0%} | {rn:.0%} | {rn - ro:+.0%} |")

    by_old, by_new = defaultdict(list), defaultdict(list)
    for r in old_c:
        by_old[r["id"]].append(r)
    for r in new_c:
        by_new[r["id"]].append(r)
    lines += [
        "",
        "| prompt | clean " + old_tag + " | clean " + new_tag + " |",
        "| --- | --- | --- |",
    ]
    for item_id in sorted(common):
        ro, rn = rate(by_old[item_id], None), rate(by_new[item_id], None)
        marker = " ⬇" if rn < ro else (" ⬆" if rn > ro else "")
        lines.append(f"| {item_id} | {ro:.0%} | {rn:.0%}{marker} |")
    only_new = sorted({r["id"] for r in new} - common)
    if only_new:
        lines += ["", f"New prompts in {new_tag}: " + ", ".join(only_new)]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("old")
    ap.add_argument("new")
    args = ap.parse_args()
    report = compare(args.old, args.new)
    out = EVAL_DIR / "results" / args.new / f"diff-vs-{args.old}.md"
    out.write_text(report, encoding="utf-8")
    print(report)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
