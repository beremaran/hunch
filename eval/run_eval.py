"""Run the English eval set against the main model and save outputs.

Each prompt gets `samples_per_prompt` sampled replies from one batched call (the way reply
candidates are generated), so latency is measured per batched call against the 10 s budget.

With --pipeline (Phase 3 on), each sample is instead the reply of the full turn pipeline
(candidate filter, judge, selection, value gate) in a fresh conversation over an empty memory
store: earlier messages of the item become the conversation's turns, its memories and one-turn
instructions are handed to the pipeline as module-provided context, and latency is the whole
reply path.

Usage:
    python -m eval.run_eval --tag phase1
    python -m eval.run_eval --tag phase3 --pipeline
    python -m eval.run_eval --tag phase1 --rescore   # re-run checks on saved outputs only
Writes eval/results/<tag>/outputs.jsonl, meta.json and summary.md.
"""

from __future__ import annotations

import argparse
import json
import statistics
import zlib
from collections import defaultdict
from pathlib import Path

from eval.scoring import REPLY_LANG, check_reply

EVAL_DIR = Path(__file__).resolve().parent
LATENCY_BUDGET_S = 10.0
SUMMARY_FLAGS = (
    "wrong_lang",
    "cjk_leak",
    "list_format",
    "missed_followup",
    "no_privacy_question",
    "unrequested_privacy_question",
    "invented_memory",
    "no_memory_admission",
    "missing",
    "denies_memory_system",
)


def build_messages(data: dict, item: dict) -> list[dict[str, str]]:
    """Persona prompt + pipeline-provided blocks (recalled memories, one-turn instructions)."""
    system = data["system_prompt"]
    if item.get("memory"):
        lines = "\n".join(f"- {m}" for m in item["memory"])
        system = f"{system}\n\n{data['memory_header']}\n{lines}"
    if item.get("turn_instructions"):
        lines = "\n".join(f"- {t}" for t in item["turn_instructions"])
        system = f"{system}\n\n{data['instruction_header']}\n{lines}"
    return [{"role": "system", "content": system}, *item["messages"]]


def item_seed(base: int, item_id: str) -> int:
    """Stable per-item seed, so adding items does not change other items' samples."""
    return base + zlib.crc32(item_id.encode("utf-8")) % 100_000


def has_flag(row: dict, flag: str) -> bool:
    return any(f.startswith(flag) for f in row["checks"]["flags"])


def summarize(rows: list[dict]) -> str:
    """Per-language table over regular prompts; expected-fail prompts are listed separately."""
    by_lang: dict[str, list[dict]] = defaultdict(list)
    by_item: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if not r.get("expected_fail"):
            by_lang[r["lang"]].append(r)
        by_item[r["id"]].append(r)

    header = ["lang", "prompts", "samples", "clean", *SUMMARY_FLAGS]
    lines = ["| " + " | ".join(header) + " |", "|" + " --- |" * len(header)]
    for lang in (REPLY_LANG,):
        rs = by_lang.get(lang, [])
        if not rs:
            continue
        n_prompts = len({r["id"] for r in rs})
        clean = sum(not r["checks"]["flags"] for r in rs)
        counts = [str(sum(has_flag(r, f) for r in rs)) for f in SUMMARY_FLAGS]
        lines.append(f"| {lang} | {n_prompts} | {len(rs)} | {clean} | " + " | ".join(counts) + " |")

    pipeline = any("chosen_by" in r for r in rows)
    latencies = [max(r["batch_latency_s"] for r in rs) for rs in by_item.values()]
    over = sum(t > LATENCY_BUDGET_S for t in latencies)
    what = "Full reply latency (pipeline), worst run" if pipeline else "Batched call latency"
    lines += [
        "",
        f"{what} per prompt: median {statistics.median(latencies):.1f} s, "
        f"max {max(latencies):.1f} s; {over}/{len(latencies)} over the "
        f"{LATENCY_BUDGET_S:.0f} s budget.",
        "",
    ]
    if pipeline:
        fallback = sum(r["chosen_by"] == "filter_fallback" for r in rows)
        gate = sum(r["chosen_by"] == "gate_fallback" for r in rows)
        rejected = sum(len(r["rejected"]) for r in rows)
        lines += [
            f"Pipeline: {fallback}/{len(rows)} replies were the filter fallback (all candidates "
            f"rejected), {gate} the value-gate fallback; {rejected} of {3 * len(rows)} "
            "candidates rejected by the filter.",
            "",
        ]
    expected = {i: rs for i, rs in by_item.items() if rs[0].get("expected_fail")}
    if expected:
        lines.append("Expected-fail prompts (known issues, not counted above):")
        for item_id, rs in expected.items():
            clean = sum(not r["checks"]["flags"] for r in rs)
            lines.append(f"- {item_id}: {clean}/{len(rs)} clean")
        lines.append("")
    for item_id, rs in by_item.items():
        clean = sum(not r["checks"]["flags"] for r in rs)
        worst = max(r["batch_latency_s"] for r in rs)
        lines.append(f"### {item_id} ({clean}/{len(rs)} clean, {worst} s)")
        for r in rs:
            flags = ", ".join(r["checks"]["flags"]) or "clean"
            if "chosen_by" in r:
                flags += f"; {r['chosen_by']}"
                if r["rejected"]:
                    flags += f", rejected {r['rejected']}"
            reply = r["reply"].replace("\n", " ")
            lines.append(f"- [{r['sample']}] ({flags}) {reply}")
        lines.append("")
    return "\n".join(lines)


def rescore(data: dict, out_dir: Path) -> None:
    by_id = {it["id"]: it for it in data["items"]}
    path = out_dir / "outputs.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    rows = [r for r in rows if r["id"] in by_id]
    for r in rows:
        r["checks"] = check_reply(by_id[r["id"]], r["reply"]).to_dict()
        r["expected_fail"] = bool(by_id[r["id"]].get("expected_fail"))
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), "utf-8")
    (out_dir / "summary.md").write_text(summarize(rows), encoding="utf-8")
    print(f"rescored {len(rows)} rows in {out_dir}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--only", default=None, help="comma-separated item ids")
    ap.add_argument("--samples", type=int, default=None, help="override samples_per_prompt")
    ap.add_argument("--rescore", action="store_true", help="re-check saved outputs, no generation")
    ap.add_argument("--pipeline", action="store_true", help="samples = full turn pipeline replies")
    args = ap.parse_args()

    data = json.loads((EVAL_DIR / "prompts.json").read_text(encoding="utf-8"))
    out_dir = EVAL_DIR / "results" / args.tag
    if args.rescore:
        rescore(data, out_dir)
        return

    import torch

    from hunch.llm.model import ChatModel, SamplingSettings

    items = data["items"]
    if args.only:
        wanted = set(args.only.split(","))
        items = [it for it in items if it["id"] in wanted]
    n = args.samples or int(data.get("samples_per_prompt", 3))

    out_dir.mkdir(parents=True, exist_ok=True)
    model = ChatModel()
    sampling = SamplingSettings()
    torch.cuda.reset_peak_memory_stats()
    if args.pipeline:
        run_pipeline(data, items, n, args.seed, model, out_dir)
        return

    rows = []
    with (out_dir / "outputs.jsonl").open("w", encoding="utf-8") as f:
        for it in items:
            seed = item_seed(args.seed, it["id"])
            res = model.generate_batch(build_messages(data, it), n, sampling, seed=seed)
            for k, (text, n_new) in enumerate(zip(res.texts, res.new_tokens, strict=True)):
                row = {
                    "id": it["id"],
                    "lang": it["lang"],
                    "category": it["category"],
                    "expected_fail": bool(it.get("expected_fail")),
                    "sample": k,
                    "seed": seed,
                    "user": it["messages"][-1]["content"],
                    "reply": text,
                    "prompt_tokens": res.prompt_tokens,
                    "new_tokens": n_new,
                    "batch_latency_s": round(res.total_s, 2),
                    "decode_steps_per_s": round(res.decode_steps_per_s, 2),
                    "checks": check_reply(it, text).to_dict(),
                }
                rows.append(row)
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            flagged = sum(bool(r["checks"]["flags"]) for r in rows[-n:])
            print(f"{it['id']}: {flagged}/{n} flagged ({res.total_s:.1f}s)", flush=True)

    status = model.kernel_status()
    meta = {
        "tag": args.tag,
        "model_id": model.settings.model_id,
        "prompts_version": data["version"],
        "samples_per_prompt": n,
        "sampling": dict(vars(sampling)),
        "base_seed": args.seed,
        "kernels": status.packages,
        "peak_allocated_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (out_dir / "summary.md").write_text(summarize(rows), encoding="utf-8")
    print(f"wrote {out_dir}")


def provided_memories(item: dict) -> list:
    """The item's memories ("(3 days ago) Said ...") as module-provided recalled lines."""
    from hunch.pipeline.prompt import RecalledLine

    out = []
    for m in item.get("memory", ()):
        age, sep, rest = m.partition(") ")
        out.append(RecalledLine(age.lstrip("("), rest) if sep else RecalledLine("earlier", m))
    return out


def run_pipeline(
    data: dict, items: list[dict], n: int, base_seed: int, model, out_dir: Path
) -> None:
    import torch

    from hunch.config import load_config
    from hunch.memory.embeddings import QwenEmbedder
    from hunch.runtime import fresh_pipeline

    e = load_config().embedding
    embedder = QwenEmbedder(e.model_id, e.device, e.query_instruction)
    rows = []
    with (out_dir / "outputs.jsonl").open("w", encoding="utf-8") as f:
        for it in items:
            seed = item_seed(base_seed, it["id"])
            for k in range(n):
                pipe = fresh_pipeline(model, embedder, seed=seed + k)
                session = pipe.new_session("u_eval")
                for m in it["messages"][:-1]:
                    pipe.store.append_turn(
                        session.conversation_id, "u_eval", m["role"], m["content"]
                    )
                r = pipe.turn(
                    session,
                    it["messages"][-1]["content"],
                    instructions=it.get("turn_instructions", ()),
                    provided_memories=provided_memories(it),
                )
                pipe.store.close()
                row = {
                    "id": it["id"],
                    "lang": it["lang"],
                    "category": it["category"],
                    "expected_fail": bool(it.get("expected_fail")),
                    "sample": k,
                    "seed": seed + k,
                    "user": it["messages"][-1]["content"],
                    "reply": r.reply,
                    "chosen_by": r.log["chosen_by"],
                    "rejected": [c["rejected"] for c in r.details["candidates"] if c["rejected"]],
                    "candidates": r.details["candidates"],
                    "quality": [c["quality"] for c in r.log["candidates"]],
                    "latency_s": r.details["latency_s"],
                    "batch_latency_s": r.details["latency_s"]["total"],
                    "checks": check_reply(it, r.reply).to_dict(),
                }
                rows.append(row)
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
            flagged = sum(bool(r["checks"]["flags"]) for r in rows[-n:])
            print(f"{it['id']}: {flagged}/{n} flagged", flush=True)
    meta = {
        "tag": out_dir.name,
        "mode": "pipeline",
        "model_id": model.settings.model_id,
        "prompts_version": data["version"],
        "samples_per_prompt": n,
        "base_seed": base_seed,
        "kernels": model.kernel_status().packages,
        "peak_allocated_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (out_dir / "summary.md").write_text(summarize(rows), encoding="utf-8")
    print(f"wrote {out_dir}")


if __name__ == "__main__":
    main()
