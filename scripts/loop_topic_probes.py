"""Phase 6 loop de-duplication (loops/dedup.py) on its blind probe set, CPU only.

eval/probes/loop_topics.json holds 60 topic pairs (30 the same matter, 30 different, 15 of them
hard negatives from the same domain), written by an agent that saw no code. Each pair is embedded
with the configured embedding model; the sweep shows, per threshold, how many same-matter pairs are
caught (a repeat is dropped) and how many different pairs are wrongly merged (a loop is lost).
A lost loop costs more than a repeated question, so the threshold should merge no different pair.

Usage:
    python -m scripts.loop_topic_probes   # writes reports/phase6/loop_topic_probes.{json,md}
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBES = ROOT / "eval" / "probes" / "loop_topics.json"
OUT = ROOT / "reports" / "phase6"
SWEEP = (0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90)


def main() -> None:
    import numpy as np

    from hunch.config import load_config
    from hunch.memory.embeddings import QwenEmbedder

    cfg = load_config()
    e = cfg.embedding
    embedder = QwenEmbedder(e.model_id, e.device, e.query_instruction)
    pairs = json.loads(PROBES.read_text(encoding="utf-8"))
    a = embedder.embed_documents([p["a"] for p in pairs])
    b = embedder.embed_documents([p["b"] for p in pairs])
    sims = [float(x) for x in np.sum(a * b, axis=1)]  # the embedder returns unit vectors
    same = [s for s, p in zip(sims, pairs, strict=True) if p["same"]]
    diff = [s for s, p in zip(sims, pairs, strict=True) if not p["same"]]
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
    (OUT / "loop_topic_probes.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    lines = [
        "# Loop topic de-duplication probes (Phase 6)",
        "",
        f"Configured same_topic_similarity: {current}. Lowest same-matter pair: "
        f"{min(same):.3f}; highest different pair: {max(diff):.3f}.",
        "",
        "| threshold | same matter caught | different pairs merged |",
        "| --- | --- | --- |",
    ]
    lines += [
        f"| {r['threshold']:.2f} | {r['caught']}/{r['same']} | {r['merged']}/{r['different']} |"
        for r in rows
    ]
    worst = sorted((p for p in out["pairs"] if not p["same"]), key=lambda p: -p["similarity"])
    lines += ["", "Closest different pairs:", ""]
    lines += [f"- {p['similarity']:.3f} {p['a']} / {p['b']}" for p in worst[:5]]
    (OUT / "loop_topic_probes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
