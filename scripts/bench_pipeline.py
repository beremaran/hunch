"""Latency and peak VRAM per turn of the full pipeline, per stage (budget: <= 10 s per reply).

A scripted 14-turn conversation over a fresh in-memory store that already holds a few memories
(so recall, the recalled-memory block and the lower traces are exercised), with after-reply work
(memory encoding, reflection, session-summary folding) timed separately since it is off the
latency path. The first turn is a warm-up (kernel compilation) and is reported but excluded from
the summary.

Phase 4: whenever a hunch chose a reply, the next two messages are "Why did you say that?" and
"Sure, think about it for a moment." (at most four times), so the report counts hunch mentions
with and without a trigger.

Usage:
    python -m scripts.bench_pipeline   # writes reports/phase4/latency.json and latency.md
"""

from __future__ import annotations

import json
import re
import statistics
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "phase4"
DAY = 86_400.0
BUDGET_S = 10.0
# Phase 4: when a hunch chose a reply, the bench asks why and then accepts the offer.
WHY = "Why did you say that?"
THINK_MORE = "Sure, think about it for a moment."
MAX_WHY = 4
HUNCH_MENTION = re.compile(r"\bhunch\b", re.IGNORECASE)

SEEDED = [  # (summary, cues, age in days, (valence, arousal), salience)
    ('They said: "Anna and I went sailing on Lake Como, best day of the summer."',
     {"person:anna": 1.0, "place:lake_como": 0.9, "emotion:joy": 0.8}, 60, (0.8, 0.6), 0.7),
    ('They said: "My grandpa used to hum Moon River while cooking. I miss him."',
     {"song:moon_river": 1.0, "emotion:grief": 0.8}, 120, (-0.7, 0.5), 0.8),
    ('They said: "Big job interview at Siemens on Friday, I am terrified."',
     {"place:siemens": 0.6, "emotion:anxious": 1.0}, 20, (-0.5, 0.8), 0.7),
    ('They said: "Started running again, 5 km this morning."',
     {"emotion:pride": 0.6}, 10, (0.6, 0.5), 0.4),
]  # fmt: skip

SCRIPT = [
    "Morning! Slept badly but coffee is helping.",
    "Moon River came on the radio in the bakery today.",
    "Do you know what that song means to me?",
    "Anna wants to go sailing again next weekend, should I say yes?",
    "Work is a lot right now, I have a deadline on Friday.",
    "Any idea how to stay focused when everything is noisy?",
    "Ha, my cat just knocked my mug off the desk.",
    "Do you remember what I told you about my job interview?",
    "It went fine in the end, I start in March!",
    "What should I cook tonight? Something quick.",
    "Wie geht es dir heute?",
    "Sorry, habit. How are you today?",
    "I think I'll go for a run before dinner.",
    "Thanks for chatting, talk tomorrow!",
]


def main() -> None:
    import numpy as np

    from hunch.config import load_config
    from hunch.llm.model import ChatModel
    from hunch.memory.embeddings import QwenEmbedder
    from hunch.memory.schema import Memory
    from hunch.runtime import fresh_pipeline

    cfg = load_config()
    model = ChatModel()
    e = cfg.embedding
    embedder = QwenEmbedder(e.model_id, e.device, e.query_instruction)
    pipe = fresh_pipeline(model, embedder, seed=11, log_dir=ROOT / "logs" / "phase4-bench")
    now = time.time()
    for i, (summary, cues, age, affect, salience) in enumerate(SEEDED):
        ep = pipe.store.append_turn(f"seed-{i}", "u_bench", "user", summary, at=now - age * DAY)
        mem = Memory(f"seed-{i}", "u_bench", "private", ep.id, summary, cues, affect, salience,
                     now - age * DAY)  # fmt: skip
        pipe.store.add_memory(mem, np.asarray(embedder.embed_documents([summary])[0]))

    session = pipe.new_session("u_bench", "c-bench")
    turns = []
    queue = list(SCRIPT)
    asked = 0
    while queue:
        text = queue.pop(0)
        r = pipe.turn(session, text)
        after = pipe.after_reply(session, r)
        trigger = r.reflection.trigger if r.reflection else None
        # Phase 4: when a hunch chose the reply, ask why and accept the offer (at most four times).
        if r.hunch is not None and asked < MAX_WHY:
            asked += 1
            queue[:0] = [WHY, THINK_MORE]
        turns.append(
            {
                "message": text,
                "reply": r.reply,
                "trigger": trigger,
                "mentions_hunch": bool(HUNCH_MENTION.search(r.reply)),
                "reflection_level": (
                    [r.reflection.level_before, r.reflection.hunch.revealed_level]
                    if r.reflection
                    else None
                ),
                "latency_s": r.details["latency_s"],
                "after_reply_s": after,
                "peak_vram_gib": r.details["peak_vram_gib"],
                "prompt_tokens": r.details["prompt_tokens"],
                "candidate_tokens": r.details["candidate_tokens"],
                "hit_cap": r.details["hit_cap"],
                "upper": [a["memory"] for a in r.details["activation"] if a["layer"] == "upper"],
                "hunch": r.log["hunch"],
                "chosen_by": r.log["chosen_by"],
            }
        )
        print(f"{r.details['latency_s']['total']:5.2f}s  {text[:40]!r} -> {r.reply[:60]!r}")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "latency.json").write_text(json.dumps(turns, indent=2), encoding="utf-8")

    measured = turns[1:]  # turn 1 is the warm-up
    stages = list(measured[0]["latency_s"])
    lines = [
        f"Full pipeline, {len(SCRIPT)} scripted turns (turn 1 = warm-up, excluded below), "
        f"budget {BUDGET_S:.0f} s per reply.",
        "",
        "| stage | median s | max s |",
        "| --- | --- | --- |",
    ]
    for st in stages:
        vals = [t["latency_s"][st] for t in measured]
        lines.append(f"| {st} | {statistics.median(vals):.2f} | {max(vals):.2f} |")
    for st in ("encode_memory", "reflection", "fold_summary"):
        vals = [t["after_reply_s"][st] for t in measured]
        lines.append(f"| after reply: {st} | {statistics.median(vals):.2f} | {max(vals):.2f} |")
    totals = [t["latency_s"]["total"] for t in measured]
    over = sum(x > BUDGET_S for x in totals)
    plain = [t for t in turns if t["trigger"] is None]
    triggered = [t for t in turns if t["trigger"] is not None]
    lines += [
        "",
        f"Reply latency: median {statistics.median(totals):.2f} s, max {max(totals):.2f} s; "
        f"{over}/{len(totals)} turns over budget. Peak VRAM per turn: max "
        f"{max(t['peak_vram_gib'] for t in turns):.2f} GiB.",
        "",
        f"Hunches formed: {sum(t['hunch'] is not None for t in turns)}/{len(turns)} turns "
        f"(chosen_by: {dict(Counter(t['chosen_by'] for t in turns))}). Replies mentioning a "
        f"hunch without a trigger: {sum(t['mentions_hunch'] for t in plain)}/{len(plain)}; "
        f"on trigger turns (why / think more): "
        f"{sum(t['mentions_hunch'] for t in triggered)}/{len(triggered)}.",
        "",
        "| # | total s | cues | candidates | judge | peak GiB | prompt tok | cand tok | chosen_by "
        "| hunch | trigger | message |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for i, t in enumerate(turns, 1):
        lat = t["latency_s"]
        lines.append(
            f"| {i} | {lat['total']:.2f} | {lat['cues']:.2f} | {lat['candidates']:.2f} "
            f"| {lat['judge']:.2f} | {t['peak_vram_gib']} | {t['prompt_tokens']} "
            f"| {max(t['candidate_tokens'] or [0])} | {t['chosen_by']} "
            f"| {'yes' if t['hunch'] else ''} | {t['trigger'] or ''} | {t['message'][:40]} |"
        )
    lines += ["", "Replies:", ""]
    lines += [f"{i}. **{t['message']}** → {t['reply']}" for i, t in enumerate(turns, 1)]
    (OUT / "latency.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
