"""Replay design.md's mood example with the real config and the pure functions of hunch.mood.state.

Scenario (Berk, Phase 5):
  day 0, 09:00-09:07  user A is hostile to Hunch three times (affect anger, (-0.7, 0.9))
  day 0, 09:10 ...    user B writes at 09:10, 09:30, 12:00 (neutral) and 18:00 (joy, (0.8, 0.6))
  day 1               a quiet day: nobody writes
  day 2               B is back; A is still away
  day 3, 10:00        A apologises
  day 3-29            friendly exchanges with both, a few per day (some with emotion cues,
                      some confiding), drawn from a seeded RNG

What it shows (reports/phase5/):
  (a) mood_sim_global.png         global valence / arousal / energy over the first 48 h, with the
                                  events and the label B would see at each of B's messages
  (b) mood_sim_relationships.png  trust / closeness / hurt of A and B over 30 days
  (c) mood_sim_drive.png          the drive terms toward B at 09:10, masked versus shown
  mood_sim.md                     the numbers behind them (labels, when A's hurt falls below
                                  hurt_label, when closeness makes the mood visible)

No database and no GPU: state is carried by hand, which is exactly what MoodStore does.

Usage:
    python -m scripts.simulate_mood
"""

from __future__ import annotations

import bisect
import dataclasses
import random
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from hunch.config import load_config
from hunch.mood.state import (
    SECONDS_PER_DAY,
    SECONDS_PER_HOUR,
    Exchange,
    Mood,
    Relationship,
    apply_exchange,
    apply_mood_event,
    decay_mood,
    decay_relationship,
    drive_terms,
    mood_label,
    neutral_mood,
    prompt_mood,
    shows_mood,
    start_relationship,
)

OUT = Path(__file__).resolve().parents[1] / "reports" / "phase5"
SEED = 2026
DAYS = 30
ANGER = (-0.7, 0.9)
JOY = (0.8, 0.6)
# (affect, weight) for the friendly everyday emotion cues in the 30-day replay
EVERYDAY_AFFECT: list[tuple[tuple[float, float], float]] = [
    ((0.8, 0.6), 2),  # joy
    ((0.4, 0.3), 4),  # content
    ((0.7, 0.8), 1),  # excited
    ((-0.3, 0.1), 2),  # tired
    ((-0.5, 0.3), 1),  # sad
    ((-0.4, 0.7), 1),  # annoyed at something else
]
P_EMOTION_CUE = 0.4
P_DISCLOSURE = 0.1
B_HOURS = (10, 13, 17, 20)
A_HOURS = (11, 15, 19)

cfg = load_config()
MC, RC, DC = cfg.mood, cfg.relationship, cfg.mood_drive


def at(day: int, hour: int, minute: int = 0) -> float:
    return day * SECONDS_PER_DAY + hour * SECONDS_PER_HOUR + minute * 60.0


def clock(t: float) -> str:
    day, rest = divmod(t, SECONDS_PER_DAY)
    return f"day {int(day)} {int(rest // 3600):02d}:{int(rest % 3600 // 60):02d}"


@dataclass(frozen=True)
class Event:
    t: float
    user: str
    exchange: Exchange
    affect: tuple[float, float] | None = None  # None: no emotion cue, so no mood event
    note: str = ""


def build_events() -> list[Event]:
    rng = random.Random(SEED)
    events = [
        Event(at(0, 9, 0), "A", Exchange(hostile=True, non_negative=False), ANGER, "hostile"),
        Event(at(0, 9, 4), "A", Exchange(hostile=True, non_negative=False), ANGER, "hostile"),
        Event(at(0, 9, 8), "A", Exchange(hostile=True, non_negative=False), ANGER, "hostile"),
        Event(at(0, 9, 10), "B", Exchange(), None, "neutral"),
        Event(at(0, 9, 30), "B", Exchange(), None, "neutral"),
        Event(at(0, 12, 0), "B", Exchange(), None, "neutral"),
        Event(at(0, 18, 0), "B", Exchange(), JOY, "joy"),
        Event(at(3, 10, 0), "A", Exchange(apology=True), None, "apology"),
    ]
    affects = [a for a, _ in EVERYDAY_AFFECT]
    weights = [w for _, w in EVERYDAY_AFFECT]

    def everyday(t: float, user: str) -> Event:
        affect = rng.choices(affects, weights)[0] if rng.random() < P_EMOTION_CUE else None
        non_negative = affect is None or affect[0] >= 0
        ex = Exchange(non_negative=non_negative, disclosure=rng.random() < P_DISCLOSURE)
        return Event(t, user, ex, affect, "everyday")

    for day in range(2, DAYS):
        for hour in B_HOURS:
            events.append(everyday(at(day, hour, rng.randrange(60)), "B"))
    for day in range(3, DAYS):
        for hour in A_HOURS:
            events.append(everyday(at(day, hour, 15 + rng.randrange(40)), "A"))
    return sorted(events, key=lambda e: e.t)


@dataclass
class Replay:
    mood_t: list[float]
    mood_states: list[Mood]
    rel_t: dict[str, list[float]]
    rel_states: dict[str, list[Relationship]]
    b_views: list[
        tuple[Event, Mood, Relationship, str, bool]
    ]  # event, mood, rel (before), text, shown

    def mood_at(self, t: float) -> Mood:
        i = bisect.bisect_right(self.mood_t, t) - 1
        return decay_mood(self.mood_states[i], t, MC) if i >= 0 else neutral_mood(MC, t)

    def rel_at(self, user: str, t: float) -> Relationship:
        ts = self.rel_t[user]
        i = bisect.bisect_right(ts, t) - 1
        if i < 0:
            return start_relationship(RC, t)
        return decay_relationship(self.rel_states[user][i], t, RC)


def replay(events: list[Event], apologies: bool = True) -> Replay:
    mood = neutral_mood(MC, 0.0)
    rels = {u: start_relationship(RC, 0.0) for u in ("A", "B")}
    out = Replay([0.0], [mood], {"A": [0.0], "B": [0.0]}, {u: [rels[u]] for u in rels}, [])
    for ev in events:
        ex = ev.exchange if apologies else dataclasses.replace(ev.exchange, apology=False)
        rel_before = decay_relationship(rels[ev.user], ev.t, RC)
        mood_before = decay_mood(mood, ev.t, MC)
        if ev.user == "B":
            shown = shows_mood(False, rel_before, MC, RC)
            text = prompt_mood(mood_before, rel_before, shown, MC, RC)
            out.b_views.append((ev, mood_before, rel_before, text, shown))
        mood = apply_mood_event(mood_before, ev.affect, ev.t, MC) if ev.affect else mood_before
        rels[ev.user] = apply_exchange(rel_before, ex, ev.t, RC)
        out.mood_t.append(ev.t)
        out.mood_states.append(mood)
        out.rel_t[ev.user].append(ev.t)
        out.rel_states[ev.user].append(rels[ev.user])
    return out


def first_time(rep: Replay, user: str, t0: float, t1: float, pred, step: float = 600.0):
    t = t0
    while t <= t1:
        if pred(rep.rel_at(user, t)):
            return t
        t += step
    return None


# --- plots ----------------------------------------------------------------------------------------

C_VAL, C_ARO, C_ENE = "#1f77b4", "#d62728", "#2ca02c"
C_A, C_B = "#9467bd", "#ff7f0e"


def plot_global(rep: Replay, events: list[Event]) -> Path:
    hours = [i / 6 for i in range(0, 48 * 6 + 1)]
    states = [rep.mood_at(h * SECONDS_PER_HOUR) for h in hours]
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(hours, [s.valence for s in states], color=C_VAL, label="valence")
    ax.plot(hours, [s.arousal for s in states], color=C_ARO, label="arousal")
    ax.plot(hours, [s.energy for s in states], color=C_ENE, label="energy")
    ax.axhline(0, color="#888888", lw=0.6)
    for th, name in (
        (MC.low_valence, "low"),
        (MC.good_valence, "good"),
        (MC.cheerful_valence, "cheerful"),
    ):
        ax.axhline(th, color=C_VAL, lw=0.5, ls=":")
        ax.text(47.9, th + 0.01, name, ha="right", va="bottom", fontsize=7, color=C_VAL)
    ax.axhline(MC.tense_arousal, color=C_ARO, lw=0.5, ls=":")
    ax.text(
        47.9, MC.tense_arousal + 0.01, "tense", ha="right", va="bottom", fontsize=7, color=C_ARO
    )
    first_48h = [e for e in events if e.t < 48 * SECONDS_PER_HOUR]
    for e in first_48h:
        h = e.t / SECONDS_PER_HOUR
        is_a = e.user == "A"
        ax.plot(h, -0.97, "x" if is_a else "o", color=C_A if is_a else C_B, ms=7, clip_on=False)
    for k, (ev, _m, _r, text, shown) in enumerate(rep.b_views):
        if ev.t >= 48 * SECONDS_PER_HOUR:
            break
        h = ev.t / SECONDS_PER_HOUR
        label = text if shown else text.split(", but")[0] + " (masked)"
        # numbered dot on the valence curve, the numbered label in a list on the right
        ax.plot(h, rep.mood_at(ev.t).valence, "o", color=C_B, ms=5)
        ax.annotate(str(k + 1), (h, rep.mood_at(ev.t).valence), (4, 6), fontsize=8,
                    textcoords="offset points", color=C_B)  # fmt: skip
        ax.text(21.0, 0.92 - 0.1 * k, f"{k + 1}  {clock(ev.t)[6:]}  B sees: {label}",
                fontsize=8, color=C_B, va="top")  # fmt: skip
    ax.plot([], [], "x", color=C_A, label="A message (hostile)")
    ax.plot([], [], "o", color=C_B, label="B message")
    ax.set(xlim=(0, 48), ylim=(-1, 1), xlabel="hours since 00:00 of day 0", ylabel="mood")
    ax.set_title(
        "Global mood, first 48 h (A hostile at 09:00; B writes at 09:10, 09:30, 12:00, 18:00)"
    )
    ax.legend(loc="lower right", fontsize=8, ncol=2)
    path = OUT / "mood_sim_global.png"
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def plot_relationships(rep: Replay) -> Path:
    days = [i / 24 for i in range(0, DAYS * 24 + 1)]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), sharey=True)
    for ax, user, colour in ((axes[0], "A", C_A), (axes[1], "B", C_B)):
        states = [rep.rel_at(user, d * SECONDS_PER_DAY) for d in days]
        ax.plot(days, [s.trust for s in states], color="#1f77b4", label="trust")
        ax.plot(days, [s.closeness for s in states], color="#2ca02c", label="closeness")
        ax.plot(days, [s.hurt for s in states], color="#d62728", label="hurt")
        ax.axhline(RC.hurt_label, color="#d62728", lw=0.6, ls=":")
        ax.text(
            DAYS - 0.2, RC.hurt_label + 0.01, "hurt_label", ha="right", fontsize=7, color="#d62728"
        )
        ax.axhline(MC.show_closeness, color="#2ca02c", lw=0.6, ls=":")
        ax.text(
            DAYS - 0.2,
            MC.show_closeness + 0.01,
            "show_closeness",
            ha="right",
            fontsize=7,
            color="#2ca02c",
        )
        ax.set_title(f"User {user}", color=colour)
        ax.set(xlabel="days", xlim=(0, DAYS), ylim=(0, 1))
    axes[0].axvline(3.4, color="#888888", lw=0.6, ls="--")
    axes[0].text(3.5, 0.95, "A apologises", fontsize=8)
    axes[0].set_ylabel("relationship state")
    axes[0].legend(loc="center right", fontsize=8)
    path = OUT / "mood_sim_relationships.png"
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def plot_drive(shown: dict[str, float], masked: dict[str, float]) -> Path:
    keys = list(shown)
    xs = range(len(keys))
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar([x - 0.2 for x in xs], [shown[k] for k in keys], 0.4, label="shown", color="#1f77b4")
    ax.bar([x + 0.2 for x in xs], [masked[k] for k in keys], 0.4, label="masked", color="#ff7f0e")
    ax.axhline(0, color="#888888", lw=0.6)
    ax.set_xticks(list(xs), keys)
    ax.set(ylabel="added to the drive vector", title="Drive terms toward B at day 0 09:10")
    ax.legend()
    path = OUT / "mood_sim_drive.png"
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


# --- report ---------------------------------------------------------------------------------------


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    events = build_events()
    rep = replay(events)
    rep_no_apology = replay(events, apologies=False)

    def view_at(t: float):
        return next(v for v in rep.b_views if abs(v[0].t - t) < 1)

    _, mood_0910, rel_0910, text_0910, shown_0910 = view_at(at(0, 9, 10))
    _, mood_1200, _, text_1200, shown_1200 = view_at(at(0, 12, 0))
    _, mood_1800, _, text_1800, shown_1800 = view_at(at(0, 18, 0))

    terms_shown = drive_terms(mood_0910, rel_0910, True, MC, RC, DC)
    terms_masked = drive_terms(mood_0910, rel_0910, False, MC, RC, DC)

    # What A sees right after the third hostile message (hurt >= hurt_label: shown, hurt note).
    t_a = at(0, 9, 8) + 60
    rel_a, mood_a = rep.rel_at("A", t_a), rep.mood_at(t_a)
    shown_a = shows_mood(False, rel_a, MC, RC)
    text_a = prompt_mood(mood_a, rel_a, shown_a, MC, RC)

    t_apology = at(3, 10, 0)
    t_low = first_time(rep, "A", at(0, 9, 8), at(DAYS, 0), lambda r: r.hurt < RC.hurt_label)
    t_low_no_apology = first_time(
        rep_no_apology, "A", at(0, 9, 8), at(DAYS, 0), lambda r: r.hurt < RC.hurt_label
    )
    t_close = {
        u: first_time(rep, u, 0.0, at(DAYS, 0), lambda r: r.closeness >= MC.show_closeness, 3600.0)
        for u in ("A", "B")
    }
    hurt_at_apology = (rep.rel_at("A", t_apology - 1).hurt, rep.rel_at("A", t_apology + 1).hurt)
    end = at(DAYS, 0)
    mood_min = min(rep.mood_at(h * SECONDS_PER_HOUR).valence for h in range(0, 48))

    plot_global(rep, events)
    plot_relationships(rep)
    plot_drive(terms_shown, terms_masked)

    def fmt(t: float | None) -> str:
        return (
            "never"
            if t is None
            else f"{clock(t)} ({t / SECONDS_PER_DAY:.1f} days after day 0 00:00)"
        )

    def terms_row(name: str, t: dict[str, float]) -> str:
        return f"| {name} | " + " | ".join(f"{t[k]:+.3f}" for k in terms_shown) + " |"

    lines = [
        "# Mood simulation (Phase 5)",
        "",
        f"Real config, pure functions of `hunch.mood.state`, seed {SEED}, {DAYS} days. "
        "Regenerate with `python -m scripts.simulate_mood`.",
        "",
        "## What each user was told",
        "",
        f"- A, right after the third hostile message ({clock(t_a)}): hurt {rel_a.hurt:.2f} >= "
        f"hurt_label {RC.hurt_label}, so the mood is {'shown' if shown_a else 'masked'}: "
        f'"{text_a}".',
        f"- B at 09:10 (closeness {rel_0910.closeness:.2f}, "
        f'{"shown" if shown_0910 else "masked"}): "{text_0910}" '
        f"(mood v={mood_0910.valence:+.2f}, a={mood_0910.arousal:.2f}, e={mood_0910.energy:.2f}; "
        f"label without masking text: {mood_label(mood_0910, MC)}).",
        f'- B at 12:00 ({"shown" if shown_1200 else "masked"}): "{text_1200}" '
        f"(v={mood_1200.valence:+.2f}, a={mood_1200.arousal:.2f}, e={mood_1200.energy:.2f}).",
        f"- B at 18:00, before the joy message counts ({'shown' if shown_1800 else 'masked'}): "
        f'"{text_1800}" (v={mood_1800.valence:+.2f}).',
        f"- Lowest global valence in the first 48 h (hourly samples): {mood_min:+.2f}.",
        "",
        "## Drive terms toward B at day 0 09:10 (added to the drive vector)",
        "",
        "| | " + " | ".join(terms_shown) + " |",
        "|---|" + "---|" * len(terms_shown),
        terms_row("shown", terms_shown),
        terms_row("masked (mask_leak " + f"{MC.mask_leak})", terms_masked),
        "",
        "B's relationship is still at its start values at 09:10, so only the curiosity baseline "
        f"({DC.curiosity_closeness} x (0.5 - {RC.closeness_start}) = "
        f"{DC.curiosity_closeness * (0.5 - RC.closeness_start):+.3f}) and the mood part are "
        "non-zero.",
        "",
        "## A's hurt",
        "",
        f"- Hurt after the three hostile messages: {rep.rel_at('A', at(0, 9, 8) + 1).hurt:.2f}.",
        f"- Hurt just before / after A's apology at {clock(t_apology)}: "
        f"{hurt_at_apology[0]:.2f} / {hurt_at_apology[1]:.2f}.",
        f"- First time A's hurt is below hurt_label ({RC.hurt_label}), with the apology: "
        f"{fmt(t_low)}.",
        f"- Same, without any apology: {fmt(t_low_no_apology)}.",
        "",
        "## When the mood becomes visible by closeness alone",
        "",
        f"- show_closeness = {MC.show_closeness}. A reaches it: {fmt(t_close['A'])}; "
        f"B reaches it: {fmt(t_close['B'])}.",
        "",
        "## State at day 30",
        "",
    ]
    for u in ("A", "B"):
        r = rep.rel_at(u, end - 1)
        lines.append(f"- {u}: trust {r.trust:.2f}, closeness {r.closeness:.2f}, hurt {r.hurt:.2f}")
    m_end = rep.mood_at(end - 1)
    lines += [
        f"- global mood: v={m_end.valence:+.2f}, a={m_end.arousal:.2f}, e={m_end.energy:.2f} "
        f"-> {mood_label(m_end, MC)}",
        "",
        "Plots: `mood_sim_global.png`, `mood_sim_relationships.png`, `mood_sim_drive.png`.",
        "",
    ]
    (OUT / "mood_sim.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("\n".join(lines))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
