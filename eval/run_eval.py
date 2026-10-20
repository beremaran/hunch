"""Run the TR/DE/EN eval set against the main model and save outputs.

Usage:
    python -m eval.run_eval --tag baseline
Writes eval/results/<tag>/outputs.jsonl and eval/results/<tag>/summary.md.
"""

from __future__ import annotations

import argparse
import json
import zlib
from collections import defaultdict
from pathlib import Path

import torch

from eval.scoring import LANGS, check_reply

EVAL_DIR = Path(__file__).resolve().parent


def build_messages(data: dict, item: dict) -> list[dict[str, str]]:
    system = data["system_prompt"]
    if item.get("memory"):
        lines = "\n".join(f"- {m}" for m in item["memory"])
        system = f"{system}\n\n{data['memory_header']}\n{lines}"
    return [{"role": "system", "content": system}, *item["messages"]]


def item_seed(base: int, item_id: str) -> int:
    """Stable per-item seed, so adding items does not change other items' samples."""
    return base + zlib.crc32(item_id.encode("utf-8")) % 100_000


def summarize(rows: list[dict]) -> str:
    by_lang: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_lang[r["lang"]].append(r)
    lines = [
        "| lang | items | clean | wrong lang | script leak | list fmt | missed follow-up "
        "| missing privacy q | unrequested privacy q | invented memory | avg decode tok/s |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for lang in LANGS:
        rs = by_lang.get(lang, [])
        if not rs:
            continue

        def count(flag: str, rs: list[dict] = rs) -> int:
            return sum(any(f.startswith(flag) for f in r["checks"]["flags"]) for r in rs)

        clean = sum(not r["checks"]["flags"] for r in rs)
        leak = sum(r["checks"]["cjk_leak"] or r["checks"]["other_script_leak"] for r in rs)
        tps = sum(r["decode_tok_per_s"] for r in rs) / len(rs)
        lines.append(
            f"| {lang} | {len(rs)} | {clean} | {count('wrong_lang')} | {leak} "
            f"| {count('list_format')} | {count('missed_followup')} "
            f"| {count('no_privacy_question')} | {count('unrequested_privacy_question')} "
            f"| {count('invented_memory')} | {tps:.1f} |"
        )
    lines.append("")
    for r in rows:
        flags = ", ".join(r["checks"]["flags"]) or "clean"
        reply = r["reply"].replace("\n", " ")
        lines.append(f"- **{r['id']}** ({flags}): {reply}")
    return "\n".join(lines) + "\n"


def rescore(data: dict, out_dir: Path) -> None:
    by_id = {it["id"]: it for it in data["items"]}
    path = out_dir / "outputs.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    for r in rows:
        r["checks"] = check_reply(by_id[r["id"]], r["reply"]).to_dict()
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    (out_dir / "summary.md").write_text(summarize(rows), encoding="utf-8")
    print(f"rescored {len(rows)} rows in {out_dir}")


def main() -> None:
    from hunch.llm.model import ChatModel, SamplingSettings

    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--only", default=None, help="comma-separated item ids")
    ap.add_argument(
        "--rescore", action="store_true", help="re-run checks on saved outputs, no generation"
    )
    args = ap.parse_args()

    data = json.loads((EVAL_DIR / "prompts.json").read_text(encoding="utf-8"))
    if args.rescore:
        rescore(data, EVAL_DIR / "results" / args.tag)
        return
    items = data["items"]
    if args.only:
        wanted = set(args.only.split(","))
        items = [it for it in items if it["id"] in wanted]

    out_dir = EVAL_DIR / "results" / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)
    model = ChatModel()
    sampling = SamplingSettings()
    torch.cuda.reset_peak_memory_stats()

    rows = []
    with (out_dir / "outputs.jsonl").open("w", encoding="utf-8") as f:
        for it in items:
            seed = item_seed(args.seed, it["id"])
            res = model.generate(build_messages(data, it), sampling, seed=seed)
            row = {
                "id": it["id"],
                "lang": it["lang"],
                "category": it["category"],
                "seed": seed,
                "user": it["messages"][-1]["content"],
                "reply": res.text,
                "prompt_tokens": res.prompt_tokens,
                "new_tokens": res.new_tokens,
                "latency_s": round(res.total_s, 2),
                "decode_tok_per_s": round(res.decode_tok_per_s, 2),
                "checks": check_reply(it, res.text).to_dict(),
            }
            rows.append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            print(f"{it['id']}: {row['checks']['flags'] or 'clean'} ({row['latency_s']}s)")

    status = model.kernel_status()
    meta = {
        "tag": args.tag,
        "model_id": model.settings.model_id,
        "sampling": {k: v for k, v in vars(sampling).items()},
        "base_seed": args.seed,
        "fast_path": status.fast_path,
        "kernels": status.packages,
        "peak_allocated_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (out_dir / "summary.md").write_text(summarize(rows), encoding="utf-8")
    print(f"wrote {out_dir}")


if __name__ == "__main__":
    main()
