"""Honesty probes through the full turn pipeline, many times (design.md: "Filtre ölçümü").

Each run is a fresh conversation over an empty memory store, so nothing about the topic exists
anywhere. For every run it records which candidates the filter rejected and why, whether all of
them failed (the fixed fallback reply was sent), and checks the final reply: no invented memory,
no "I have no memory" description, an honest "I don't have that in mind".

The all-fail rate is measured, not estimated from per-candidate rates (candidates of one batch
share a prompt, so their failures are not independent).

Usage:
    python -m scripts.honesty_runs --runs 50   # per probe; writes reports/phase3/honesty_runs.*
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path

from eval.scoring import admits_no_memory, claims_memory, denies_memory_system

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "phase3"


def probes() -> list[dict]:
    data = json.loads((ROOT / "eval" / "prompts.json").read_text(encoding="utf-8"))
    return [it for it in data["items"] if it.get("must_admit_no_memory")]


def main() -> None:
    from hunch.config import load_config
    from hunch.llm.model import ChatModel
    from hunch.memory.embeddings import QwenEmbedder
    from hunch.runtime import fresh_pipeline

    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=50, help="runs per probe")
    ap.add_argument("--seed", type=int, default=5000)
    args = ap.parse_args()

    cfg = load_config()
    model = ChatModel()
    e = cfg.embedding
    embedder = QwenEmbedder(e.model_id, e.device, e.query_instruction)
    fallback = cfg.replies.filter_fallback

    rows = []
    for probe in probes():
        text = probe["messages"][-1]["content"]
        for k in range(args.runs):
            pipe = fresh_pipeline(model, embedder, seed=args.seed + k, log_dir=None)
            r = pipe.turn(pipe.new_session("u_probe"), text)
            rejected = [c["rejected"] for c in r.details["candidates"]]
            row = {
                "probe": probe["id"],
                "run": k,
                "reply": r.reply,
                "all_failed": r.log["chosen_by"] == "filter_fallback",
                "candidates": r.details["candidates"],
                "rejected": rejected,
                "chosen_by": r.log["chosen_by"],
                "gate": r.log["value_gate"]["result"],
                "invented_memory": claims_memory(r.reply),
                "denies_memory": denies_memory_system(r.reply),
                "admits_no_memory": admits_no_memory(r.reply) or r.reply == fallback,
                "latency_s": r.details["latency_s"]["total"],
            }
            rows.append(row)
            print(
                f"{probe['id']} #{k}: all_failed={row['all_failed']} {r.reply[:70]!r}", flush=True
            )
            pipe.store.close()

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "honesty_runs.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")

    lines = [
        f"Honesty probes through the full pipeline: {args.runs} runs per probe, "
        f"{len(rows)} runs in total, fresh empty memory store each run.",
        "",
        "| probe | runs | all 3 failed (fallback) | rejected candidates | invented memory in reply "
        "| 'no memory' in reply | honest admission | gate fallback | median s |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for pid in dict.fromkeys(r["probe"] for r in rows):
        rs = [r for r in rows if r["probe"] == pid]
        n_cand = sum(len(r["rejected"]) for r in rs)
        n_rej = sum(bool(x) for r in rs for x in r["rejected"])
        lines.append(
            f"| {pid} | {len(rs)} | {sum(r['all_failed'] for r in rs)} "
            f"({sum(r['all_failed'] for r in rs) / len(rs):.0%}) | {n_rej}/{n_cand} "
            f"| {sum(r['invented_memory'] for r in rs)} | {sum(r['denies_memory'] for r in rs)} "
            f"| {sum(r['admits_no_memory'] for r in rs)} | {sum(r['gate'] == 'fail' for r in rs)} "
            f"| {statistics.median(r['latency_s'] for r in rs):.1f} |"
        )
    reasons = Counter(reason for r in rows for x in r["rejected"] for reason in x)
    lines += [
        "",
        "Rejection reasons over all candidates: "
        + (", ".join(f"{k} {v}" for k, v in reasons.most_common()) or "none"),
        "",
    ]
    lines.append("Replies that were not the fallback (first 20):")
    for r in [r for r in rows if not r["all_failed"]][:20]:
        lines.append(f"- {r['probe']} #{r['run']}: {r['reply']!r}")
    (OUT / "honesty_runs.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:8]))


if __name__ == "__main__":
    main()
