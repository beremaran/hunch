"""Simulate recall over 6 months with the activation engine and the parameters in config.

50 hand-written memories (two users) are created over the first five months. Every simulated day a
message mentions people, places and emotions at fixed rates; of the memories that share a cue with
the message and cross tau_upper, the top `max_upper_per_turn` per user are recalled, which adds an
access time (rehearsal). On top of
that, probes measure recall probability (200 noise draws) with a memory's common cue (a frequent
name) and with its rare cue (a song).

Checks:
  (a) some memories are always recalled: P(recall | common cue) >= 0.9 in every month after creation
  (b) some never come back without a rare cue: P(recall | common cue) <= 0.05 from day 60 on,
      while P(recall | rare cue) >= 0.9
  (c) a rare cue beats a common cue: the song adds more activation than the frequent name
  (d) a common name counts fully in context: "Anna" + "sailing" brings back the sailing memory,
      "Anna" alone does not; the name itself adds more when the context matches

Usage:
    python scripts/simulate_recall.py            # writes reports/phase2/
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import replace
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from hunch.config import load_config
from hunch.memory.schema import Memory
from hunch.recall.activation import (
    SECONDS_PER_DAY,
    ActivationParams,
    activation,
    fan_from_cue_sets,
    spreading,
)

OUT = Path(__file__).resolve().parents[1] / "reports" / "phase2"
DAYS = 180
SEED = 2026
PROBE_DRAWS = 200
NEUTRAL_MOOD = (0.0, 0.5)

# (day, owner, summary, cues, valence, arousal, salience, group)
# group: "flashbulb" (should always come back), "song" (only a song brings it back), "everyday"
MEMORIES: list[tuple] = [
    (2, "u_anna", "Anna's wedding; first dance to Hallelujah",
     {"person:anna": 0.9, "person:tom": 0.9, "song:hallelujah": 1.0, "place:lisbon": 0.6},
     0.9, 0.9, 0.95, "flashbulb"),
    (20, "u_anna", "Anna's car accident on the motorway",
     {"person:anna": 1.0, "emotion:fear": 0.9, "place:motorway": 0.8}, -0.9, 0.95, 0.9, "flashbulb"),
    (45, "u_ben", "Ben got the promotion he had worked two years for",
     {"person:ben": 1.0, "place:office": 0.7, "emotion:joy": 0.8}, 0.8, 0.85, 0.85, "flashbulb"),
    (8, "u_anna", "Anna mentioned Wonderwall was playing in the café",
     {"person:anna": 0.5, "song:wonderwall": 0.9, "place:cafe": 0.5}, 0.2, 0.3, 0.2, "song"),
    (15, "u_anna", "Anna hummed Bohemian Rhapsody while cooking",
     {"person:anna": 0.5, "song:bohemian_rhapsody": 0.9, "place:kitchen": 0.4}, 0.3, 0.3, 0.2, "song"),
    (25, "u_anna", "Anna heard Yellow by Coldplay on the train",
     {"person:anna": 0.5, "song:yellow": 0.9, "place:train": 0.5}, 0.1, 0.3, 0.2, "song"),
    (1, "u_anna", "Anna started a pottery class", {"person:anna": 0.7, "phrase:pottery": 0.8}, 0.4, 0.4, 0.3, "everyday"),
    (3, "u_ben", "Ben's heating broke", {"person:ben": 0.7, "place:flat": 0.6, "emotion:annoyed": 0.5}, -0.4, 0.5, 0.4, "everyday"),
    (5, "u_anna", "Anna went jogging in the park", {"person:anna": 0.6, "place:park": 0.6}, 0.3, 0.3, 0.2, "everyday"),
    (6, "u_ben", "Ben watched Dune", {"person:ben": 0.6, "film:dune": 0.8}, 0.4, 0.4, 0.2, "everyday"),
    (9, "u_anna", "Anna's sister Lisa visited", {"person:anna": 0.6, "person:lisa": 0.9}, 0.5, 0.4, 0.4, "everyday"),
    (11, "u_ben", "Ben had a long meeting", {"person:ben": 0.5, "place:office": 0.7, "emotion:tired": 0.5}, -0.2, 0.3, 0.2, "everyday"),
    (12, "u_anna", "Anna argued with her landlord", {"person:anna": 0.6, "place:flat": 0.6, "emotion:anger": 0.7}, -0.6, 0.7, 0.5, "everyday"),
    (14, "u_ben", "Ben's dentist appointment", {"person:ben": 0.6, "date:2026-05-14": 0.7}, -0.2, 0.3, 0.3, "everyday"),
    (17, "u_anna", "Anna baked bread", {"person:anna": 0.6, "place:kitchen": 0.5}, 0.4, 0.2, 0.1, "everyday"),
    (19, "u_ben", "Ben visited Berlin for work", {"person:ben": 0.6, "place:berlin": 0.8}, 0.2, 0.4, 0.3, "everyday"),
    (22, "u_anna", "Anna felt lonely on Sunday", {"person:anna": 0.6, "emotion:sad": 0.8}, -0.5, 0.4, 0.4, "everyday"),
    (24, "u_ben", "Ben bought a bike", {"person:ben": 0.6, "phrase:bike": 0.7}, 0.4, 0.4, 0.2, "everyday"),
    (27, "u_anna", "Anna watched Amélie again", {"person:anna": 0.5, "film:amelie": 0.8}, 0.5, 0.3, 0.2, "everyday"),
    (30, "u_ben", "Ben's flatmate moved out", {"person:ben": 0.6, "place:flat": 0.6}, -0.1, 0.4, 0.3, "everyday"),
    (33, "u_anna", "Anna's job interview at a bank", {"person:anna": 0.7, "place:office": 0.5, "emotion:anxious": 0.7}, 0.0, 0.7, 0.6, "everyday"),
    (35, "u_ben", "Ben ran a 10k", {"person:ben": 0.6, "place:park": 0.5, "emotion:joy": 0.5}, 0.6, 0.6, 0.4, "everyday"),
    (38, "u_anna", "Anna went sailing with Tom on the lake", {"person:anna": 0.7, "phrase:sailing": 0.8, "person:tom": 0.5}, 0.5, 0.4, 0.3, "sailing"),
    (40, "u_ben", "Ben's cat was sick", {"person:ben": 0.6, "emotion:worry": 0.7}, -0.5, 0.6, 0.5, "everyday"),
    (43, "u_anna", "Anna repainted the hallway", {"person:anna": 0.5, "place:flat": 0.5}, 0.2, 0.2, 0.1, "everyday"),
    (48, "u_ben", "Ben read a book about Lisbon", {"person:ben": 0.5, "place:lisbon": 0.6}, 0.3, 0.2, 0.1, "everyday"),
    (50, "u_anna", "Anna lost her keys", {"person:anna": 0.5, "emotion:annoyed": 0.5}, -0.3, 0.4, 0.2, "everyday"),
    (53, "u_ben", "Ben met an old friend Tom", {"person:ben": 0.6, "person:tom": 0.7}, 0.5, 0.4, 0.3, "everyday"),
    (56, "u_anna", "Anna got a cold", {"person:anna": 0.5, "emotion:tired": 0.5}, -0.3, 0.3, 0.2, "everyday"),
    (59, "u_ben", "Ben planned a trip to Berlin", {"person:ben": 0.6, "place:berlin": 0.7}, 0.4, 0.4, 0.3, "everyday"),
    (62, "u_anna", "Anna's birthday dinner", {"person:anna": 0.7, "date:2026-06-21": 0.8, "emotion:joy": 0.6}, 0.7, 0.6, 0.5, "everyday"),
    (66, "u_ben", "Ben's laptop died", {"person:ben": 0.6, "emotion:annoyed": 0.6}, -0.5, 0.5, 0.3, "everyday"),
    (70, "u_anna", "Anna visited Lisbon", {"person:anna": 0.6, "place:lisbon": 0.8}, 0.6, 0.5, 0.4, "everyday"),
    (74, "u_ben", "Ben started learning Spanish", {"person:ben": 0.6, "phrase:spanish": 0.7}, 0.3, 0.3, 0.2, "everyday"),
    (78, "u_anna", "Anna's colleague quit", {"person:anna": 0.5, "place:office": 0.6}, -0.1, 0.3, 0.2, "everyday"),
    (82, "u_ben", "Ben watched Oppenheimer", {"person:ben": 0.5, "film:oppenheimer": 0.8}, 0.3, 0.4, 0.2, "everyday"),
    (86, "u_anna", "Anna couldn't sleep before a deadline", {"person:anna": 0.5, "emotion:anxious": 0.7}, -0.4, 0.6, 0.3, "everyday"),
    (90, "u_ben", "Ben fixed his bike", {"person:ben": 0.5, "phrase:bike": 0.7}, 0.3, 0.2, 0.1, "everyday"),
    (95, "u_anna", "Anna took Lisa to a concert", {"person:anna": 0.6, "person:lisa": 0.8, "emotion:joy": 0.6}, 0.7, 0.6, 0.4, "everyday"),
    (100, "u_ben", "Ben moved desks at the office", {"person:ben": 0.4, "place:office": 0.6}, 0.0, 0.2, 0.1, "everyday"),
    (105, "u_anna", "Anna started yoga", {"person:anna": 0.5, "phrase:yoga": 0.7}, 0.4, 0.3, 0.2, "everyday"),
    (110, "u_ben", "Ben's sister had a baby", {"person:ben": 0.7, "emotion:joy": 0.7}, 0.8, 0.6, 0.6, "everyday"),
    (115, "u_anna", "Anna's train was cancelled", {"person:anna": 0.5, "place:train": 0.5, "emotion:annoyed": 0.5}, -0.4, 0.4, 0.2, "everyday"),
    (120, "u_ben", "Ben went to Berlin again", {"person:ben": 0.5, "place:berlin": 0.7}, 0.3, 0.3, 0.2, "everyday"),
    (125, "u_anna", "Anna adopted a dog", {"person:anna": 0.7, "phrase:dog": 0.8, "emotion:joy": 0.7}, 0.8, 0.7, 0.6, "everyday"),
    (130, "u_ben", "Ben had a bad flu", {"person:ben": 0.6, "emotion:tired": 0.6}, -0.5, 0.4, 0.3, "everyday"),
    (135, "u_anna", "Anna's landlord raised the rent", {"person:anna": 0.6, "place:flat": 0.6, "emotion:anger": 0.6}, -0.6, 0.6, 0.5, "everyday"),
    (140, "u_ben", "Ben watched Dune Part Two", {"person:ben": 0.5, "film:dune": 0.8}, 0.5, 0.4, 0.2, "everyday"),
    (145, "u_anna", "Anna planned Christmas with Lisa", {"person:anna": 0.6, "person:lisa": 0.7}, 0.5, 0.4, 0.3, "everyday"),
    (150, "u_ben", "Ben's bike was stolen", {"person:ben": 0.6, "phrase:bike": 0.8, "emotion:anger": 0.7}, -0.7, 0.7, 0.5, "everyday"),
]  # fmt: skip

# Daily mention rates of cues in conversation (songs essentially never come up by themselves).
DAILY_MENTIONS = {
    "person:anna": 0.35, "person:ben": 0.25, "person:lisa": 0.05, "person:tom": 0.03,
    "place:office": 0.10, "place:flat": 0.08, "place:berlin": 0.03, "place:lisbon": 0.02,
    "emotion:joy": 0.10, "emotion:annoyed": 0.08, "emotion:tired": 0.08, "emotion:anxious": 0.05,
}  # fmt: skip


def build_memories() -> list[tuple[Memory, str]]:
    out = []
    for i, (day, owner, summary, cues, val, aro, sal, group) in enumerate(MEMORIES):
        m = Memory(
            id=f"m{i:02d}", owner_user=owner, privacy="general", episode_ref=f"e{i:02d}",
            summary=summary, cues=cues, affect=(val, aro), salience=sal,
            created_at=day * SECONDS_PER_DAY,
        )  # fmt: skip
        out.append((m, group))
    return out


def common_cue(m: Memory) -> str:
    return next(c for c in m.cues if c.startswith("person:"))


def rare_cue(m: Memory) -> str | None:
    return next((c for c in m.cues if c.startswith("song:")), None)


def p_recall(
    m: Memory, now_day: float, cue: str | None, fan, params: ActivationParams, rng
) -> float:
    cues = {cue: 1.0} if cue else {}
    hits = sum(
        activation(m, now_day * SECONDS_PER_DAY, cues, fan, NEUTRAL_MOOD, params, rng).total
        > params.tau_upper
        for _ in range(PROBE_DRAWS)
    )
    return hits / PROBE_DRAWS


def expected_activation(m: Memory, now_day: float, cue: str | None, fan, params) -> float:
    quiet = replace(params, noise_s=0.0)
    cues = {cue: 1.0} if cue else {}
    return activation(
        m, now_day * SECONDS_PER_DAY, cues, fan, NEUTRAL_MOOD, quiet, np.random.default_rng(0)
    ).total


def simulate(params: ActivationParams, capacity: int, seed: int = SEED) -> dict:
    """Run the 6-month simulation; returns checks plus the data the plots need."""
    rng = np.random.default_rng(seed)
    items = build_memories()
    groups = {m.id: g for m, g in items}
    fan_counts = Counter(c for m, _ in items for c in m.cues)
    fan = fan_from_cue_sets([frozenset(m.cues) for m, _ in items])
    state: dict[str, Memory] = {}
    access_log: dict[str, list[float]] = {m.id: [] for m, _ in items}

    weeks = DAYS // 7
    p_common = np.full((len(items), weeks), np.nan)
    p_rare = np.full((len(items), weeks), np.nan)
    traces = {mid: {"day": [], "none": [], "common": [], "rare": []} for mid in groups}

    for day in range(DAYS):
        for m, _ in items:
            if m.created_at / SECONDS_PER_DAY == day:
                state[m.id] = m
        # today's conversation: the top `capacity` cued memories above tau_upper per owner are
        # recalled into context, and so rehearsed
        message = {c: 1.0 for c, p in DAILY_MENTIONS.items() if rng.random() < p}
        now = (day + 0.5) * SECONDS_PER_DAY
        for owner in ("u_anna", "u_ben"):
            scored = [
                (activation(m, now, message, fan, NEUTRAL_MOOD, params, rng).total, mid)
                for mid, m in state.items()
                if m.owner_user == owner and message.keys() & m.cues.keys()
            ]
            above = sorted((a, mid) for a, mid in scored if a > params.tau_upper)[::-1]
            for _, mid in above[:capacity]:
                m = state[mid]
                access_log[mid].append(day + 0.5)
                state[mid] = replace(m, access_times=(*m.access_times, now))
        # probes at the end of the day (they do not rehearse)
        for row, (m0, _) in enumerate(items):
            if m0.id not in state:
                continue
            m = state[m0.id]
            t = day + 1.0
            tr = traces[m.id]
            tr["day"].append(t)
            tr["none"].append(expected_activation(m, t, None, fan, params))
            tr["common"].append(expected_activation(m, t, common_cue(m), fan, params))
            rc = rare_cue(m)
            tr["rare"].append(expected_activation(m, t, rc, fan, params) if rc else np.nan)
            if day % 7 == 6:
                w = day // 7
                p_common[row, w] = p_recall(m, t, common_cue(m), fan, params, rng)
                if rc:
                    p_rare[row, w] = p_recall(m, t, rc, fan, params, rng)

    # --- checks ---------------------------------------------------------------------------------
    ids = [m.id for m, _ in items]
    always = []
    for row, mid in enumerate(ids):
        created_week = int(items[row][0].created_at / SECONDS_PER_DAY // 7)
        monthly = [
            np.nanmin(p_common[row, w : w + 4])
            for w in range(created_week + 1, weeks, 4)
            if not np.all(np.isnan(p_common[row, w : w + 4]))
        ]
        if monthly and min(monthly) >= 0.9:
            always.append(mid)
    late = slice(60 // 7, weeks)
    only_rare = [
        mid
        for row, mid in enumerate(ids)
        if rare_cue(items[row][0])
        and np.nanmax(p_common[row, late]) <= 0.05
        and np.nanmin(p_rare[row, late]) >= 0.9
    ]
    boosts = []
    for m, g in items:
        if g == "song":
            song = spreading({rare_cue(m): 1.0}, m.cues, fan, params.spreading_s,
                             params.cue_type_weights, params.min_cue_strength)  # fmt: skip
            name = spreading({common_cue(m): 1.0}, m.cues, fan, params.spreading_s,
                             params.cue_type_weights, params.min_cue_strength)  # fmt: skip
            boosts.append({"memory": m.id, "song": round(song, 3), "name": round(name, 3)})
    # (d) a common name counts fully in context: "Anna" + "sailing" vs "Anna" alone, at day 179
    sail = next(m for m, g in items if g == "sailing")
    sail_now = state[sail.id]
    others = [state[m.id] for m, g in items if g != "sailing" and "person:anna" in m.cues]
    end = 179.0

    def expected(m: Memory, cues: dict[str, float]) -> float:
        quiet = replace(params, noise_s=0.0)
        return activation(m, end * SECONDS_PER_DAY, cues, fan, NEUTRAL_MOOD, quiet,
                          np.random.default_rng(0)).total  # fmt: skip

    anna_only = {"person:anna": 1.0}
    anna_sailing = {"person:anna": 1.0, "phrase:sailing": 1.0}
    name_term = {
        "anna_alone": spreading(anna_only, sail.cues, fan, params.spreading_s,
                                params.cue_type_weights, params.min_cue_strength),
        "anna_in_sailing_context": spreading(anna_sailing, sail.cues, fan, params.spreading_s,
                                             params.cue_type_weights, params.min_cue_strength)
        - spreading({"phrase:sailing": 1.0}, sail.cues, fan, params.spreading_s,
                    params.cue_type_weights, params.min_cue_strength),
    }  # fmt: skip
    rank_alone = sorted([expected(m, anna_only) for m in [sail_now, *others]], reverse=True).index(
        expected(sail_now, anna_only)
    )
    sail_in_context = expected(sail_now, anna_sailing)
    d_check = {
        "pass": sail_in_context > params.tau_upper
        and expected(sail_now, anna_only) <= params.tau_upper
        and name_term["anna_in_sailing_context"] > name_term["anna_alone"],
        "memory": sail.id,
        "A_anna_alone": round(expected(sail_now, anna_only), 3),
        "A_anna_and_sailing": round(sail_in_context, 3),
        "rank_among_anna_memories_with_anna_alone": rank_alone + 1,
        "name_term": {k: round(v, 3) for k, v in name_term.items()},
    }

    checks = {
        "d_name_in_context": d_check,
        "a_always_recalled": {"pass": bool(always), "memories": always,
                              "groups": [groups[m] for m in always]},
        "b_only_rare_cue": {"pass": bool(only_rare), "memories": only_rare},
        "c_rare_beats_common": {"pass": all(b["song"] > b["name"] for b in boosts),
                                "boosts": boosts},
    }  # fmt: skip
    return {
        "items": items, "groups": groups, "fan_counts": fan_counts, "fan": fan, "traces": traces,
        "access_log": access_log, "p_common": p_common, "p_rare": p_rare, "checks": checks,
        "boosts": boosts,
    }  # fmt: skip


def main() -> None:
    cfg = load_config()
    params = cfg.activation
    capacity = cfg.recall.max_upper_per_turn
    sim = simulate(params, capacity)
    items, traces, access_log = sim["items"], sim["traces"], sim["access_log"]
    p_common, p_rare, checks, boosts = sim["p_common"], sim["p_rare"], sim["checks"], sim["boosts"]
    fan_counts, fan = sim["fan_counts"], sim["fan"]
    rehearsals = {mid: len(v) for mid, v in access_log.items()}

    # --- plots ----------------------------------------------------------------------------------
    OUT.mkdir(parents=True, exist_ok=True)
    pick = {
        "m00": "flashbulb: wedding (Hallelujah)",
        "m01": "flashbulb: car accident",
        "m03": "song memory: Wonderwall",
        "m06": "everyday: pottery class",
    }
    fig, axes = plt.subplots(2, 2, figsize=(12, 7), sharex=True, sharey=True)
    for ax, (mid, title) in zip(axes.flat, pick.items(), strict=True):
        tr = traces[mid]
        ax.plot(tr["day"], tr["none"], color="0.6", label="no cue")
        name = common_cue(next(m for m, _ in items if m.id == mid))
        ax.plot(tr["day"], tr["common"], color="tab:blue", label=f"common cue ({name})")
        if not np.all(np.isnan(tr["rare"])):
            ax.plot(tr["day"], tr["rare"], color="tab:red", label="rare cue (song)")
        for d in access_log[mid]:
            ax.axvline(d, color="tab:green", alpha=0.15, lw=1)
        ax.axhline(params.tau_upper, color="black", ls="--", lw=1)
        ax.axhline(params.tau_lower, color="black", ls=":", lw=1)
        ax.set_title(f"{mid} {title} ({rehearsals[mid]} recalls)", fontsize=10)
        ax.legend(fontsize=7, loc="upper right")
    for ax in axes[1]:
        ax.set_xlabel("day")
    for ax in axes[:, 0]:
        ax.set_ylabel("activation A (no noise)")
    fig.suptitle(
        f"Activation over 6 months (dashed: tau_upper={params.tau_upper}, "
        f"dotted: tau_lower={params.tau_lower}; green: recalls in conversation)"
    )
    fig.tight_layout()
    fig.savefig(OUT / "activation_over_time.png", dpi=120)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(13, 9), sharey=True)
    labels = [f"{m.id} [{g[0].upper()}] {m.summary[:34]}" for m, g in items]
    for ax, data, title in (
        (axes[0], p_common, "P(recall) with the common cue (the person's name)"),
        (axes[1], p_rare, "P(recall) with the rare cue (song memories only)"),
    ):
        im = ax.imshow(data, aspect="auto", cmap="viridis", vmin=0, vmax=1)
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("week")
    axes[0].set_yticks(range(len(labels)), labels, fontsize=6)
    fig.colorbar(im, ax=axes, shrink=0.6, label="P(A > tau_upper)")
    fig.suptitle("Recall probability per week (F = flashbulb, S = song, E = everyday)")
    fig.savefig(OUT / "recall_heatmap.png", dpi=120, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(boosts))
    ax.bar(x - 0.2, [b["song"] for b in boosts], 0.4, label="rare cue: song (fan 1)",
           color="tab:red")  # fmt: skip
    ax.bar(x + 0.2, [b["name"] for b in boosts], 0.4,
           label=f"common cue: person:anna (fan {fan('person:anna', frozenset())})", color="tab:blue")  # fmt: skip
    ax.set_xticks(x, [b["memory"] for b in boosts])
    ax.set_ylabel("spreading activation added")
    ax.set_title("Fan effect: a rare cue beats a frequent name")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUT / "cue_boost.png", dpi=120)
    plt.close(fig)

    report = {
        "params": {
            f: (dict(getattr(params, f)) if f == "cue_type_weights" else getattr(params, f))
            for f in params.__dataclass_fields__
        },
        "max_upper_per_turn": capacity,
        "seed": SEED,
        "fan": dict(sorted(fan_counts.items(), key=lambda kv: -kv[1])),
        "rehearsals": rehearsals,
        "checks": checks,
    }  # fmt: skip
    (OUT / "simulation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for name, c in checks.items():
        detail = c.get("memories", c.get("boosts", {k: v for k, v in c.items() if k != "pass"}))
        print(f"{name}: {'PASS' if c['pass'] else 'FAIL'}  {detail}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
