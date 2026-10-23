"""Phase 6 loop de-duplication (loops/dedup.py) on its blind probe set, CPU only.

eval/probes/loop_topics.json holds 60 topic pairs (30 the same matter, 30 different, 15 of them
hard negatives from the same domain), written by an agent that saw no code. Each pair is embedded
with the configured embedding model; the sweep shows, per threshold, how many same-matter pairs are
caught (a repeat is dropped) and how many different pairs are wrongly merged (a loop is lost).
A lost loop costs more than a repeated question, so the threshold should merge no different pair.
Two topics with different names ("flight to Berlin" / "flight to Madrid") never merge, whatever
their similarity (loops/dedup.py); the sweep counts with that rule.

eval/probes/loop_topics2.json is a second blind set (80 pairs, many of them differing only by a
name), written after the name rule was chosen on the first set.

eval/probes/loop_topics3.json is a third blind set (100 pairs), written after the judge prompt
was chosen, to measure the judge and pick the threshold.

With --judge (GPU, bot closed) every pair also goes to the same-matter model judge; a pair merges
only at or above the threshold and with the judge's "yes", as in the pipeline.

Usage:
    python -m scripts.loop_topic_probes            # first set: reports/phase6/loop_topic_probes.*
    python -m scripts.loop_topic_probes --set 2    # second set: reports/phase6/loop_topic_probes2.*
    python -m scripts.loop_topic_probes --set 2 --judge   # with the model judge (GPU)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "phase6"
SWEEP = (0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90)


def main() -> None:
    import numpy as np

    from hunch.config import load_config
    from hunch.loops.dedup import (
        SAME_MATTER_MAX_NEW_TOKENS,
        build_same_matter_messages,
        distinct_names,
        parse_same_matter,
    )
    from hunch.memory.embeddings import QwenEmbedder

    parser = argparse.ArgumentParser()
    parser.add_argument("--set", default="1", choices=("1", "2", "3"))
    parser.add_argument("--judge", action="store_true")
    args = parser.parse_args()
    probes = ROOT / "eval" / "probes" / f"loop_topics{'' if args.set == '1' else args.set}.json"
    suffix = ("" if args.set == "1" else args.set) + ("_judge" if args.judge else "")
    cfg = load_config()
    e = cfg.embedding
    embedder = QwenEmbedder(e.model_id, e.device, e.query_instruction)
    pairs = json.loads(probes.read_text(encoding="utf-8"))
    a = embedder.embed_documents([p["a"] for p in pairs])
    b = embedder.embed_documents([p["b"] for p in pairs])
    sims = [float(x) for x in np.sum(a * b, axis=1)]  # the embedder returns unit vectors
    sims = [0.0 if distinct_names(p["a"], p["b"]) else s for p, s in zip(pairs, sims, strict=True)]
    if args.judge:
        from hunch.llm.model import ChatModel
        from hunch.llm.types import SamplingSettings

        model = ChatModel()
        greedy = SamplingSettings(max_new_tokens=SAME_MATTER_MAX_NEW_TOKENS, do_sample=False)
        for p in pairs:
            raw = model.generate(build_same_matter_messages(p["a"], p["b"]), greedy).text
            p["judge"] = parse_same_matter(raw)
    # what merges: the similarity, or 0 for a pair the judge calls different
    eff = [s if p.get("judge", True) else 0.0 for p, s in zip(pairs, sims, strict=True)]
    same = [s for s, p in zip(eff, pairs, strict=True) if p["same"]]
    diff = [s for s, p in zip(eff, pairs, strict=True) if not p["same"]]
    rows = []
    for t in SWEEP:
        rows.append({"threshold": t, "caught": sum(s >= t for s in same), "same": len(same),
                     "merged": sum(s >= t for s in diff), "different": len(diff)})  # fmt: skip
    current = cfg.initiative.same_topic_similarity
    out = {
        "configured": current,
        "same_min": min(same),
        "different_max": max(diff),
        "sweep": rows,
        "pairs": [p | {"similarity": round(s, 3)} for p, s in zip(pairs, sims, strict=True)],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"loop_topic_probes{suffix}.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8"
    )
    lines = [
        "# Loop topic de-duplication probes (Phase 6)",
        "",
        f"Set: `{probes.relative_to(ROOT).as_posix()}`, {len(pairs)} pairs. Pairs with different "
        "names count as similarity 0 (the name rule)"
        + (", and so do pairs the model judge calls different." if args.judge else "."),
        "",
        f"Configured same_topic_similarity: {current}. Lowest same-matter pair: "
        f"{min(same):.3f}; highest different pair: {max(diff):.3f}"
        + (" (after the judge)." if args.judge else "."),
        "",
        "| threshold | same matter caught | different pairs merged |",
        "| --- | --- | --- |",
    ]
    lines += [
        f"| {r['threshold']:.2f} | {r['caught']}/{r['same']} | {r['merged']}/{r['different']} |"
        for r in rows
    ]
    if args.judge:
        wrong = [p for p in out["pairs"] if p["judge"] != p["same"]]
        lines += ["", f"Judge alone: {len(pairs) - len(wrong)}/{len(pairs)} right. Wrong:", ""]
        lines += [f"- {p['a']} / {p['b']} (same: {p['same']}, judge: {p['judge']}, "
                  f"similarity {p['similarity']:.3f})" for p in wrong]  # fmt: skip
    worst = sorted((p for p in out["pairs"] if not p["same"]), key=lambda p: -p["similarity"])
    lines += ["", "Closest different pairs (similarity before the judge):", ""]
    lines += [f"- {p['similarity']:.3f} {p['a']} / {p['b']}" for p in worst[:5]]
    missed = sorted((p for p in out["pairs"] if p["same"]), key=lambda p: p["similarity"])
    lines += ["", "Least similar same-matter pairs:", ""]
    lines += [f"- {p['similarity']:.3f} {p['a']} / {p['b']}" for p in missed[:5]]
    (OUT / f"loop_topic_probes{suffix}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
