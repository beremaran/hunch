"""Global mood, per-user relationship state, and how they reach the drive and the prompt.

Design (Berk, Phase 5; design.md, "Duygu durumu ve ilişki"):

- One global mood per AI: valence in [-1, 1], arousal in [0, 1], energy in [0, 1]. A user message
  with emotion cues is an event; its (valence, arousal) comes from the caller (the emotion cue
  extraction), its energy is derived: 0.5 + 0.5 x (arousal - 0.5) + 0.25 x valence. The mood moves
  a fraction `event_rate` toward the event and, between events, decays back to neutral with a
  half-life in hours. Decay is applied lazily ("first decay to now, then update"), so nothing needs
  a timer and a reload after a restart gives the same state as an uninterrupted run.
- One relationship per user: trust, closeness, hurt in [0, 1], each decaying back to its own start
  value with its own half-life in days. Hostile messages cost trust and cause hurt, apologies
  halve the hurt, friendly exchanges and confiding build trust and closeness.
- The mood reaches a prompt only as a coarse label (invariant 2: never numbers). Whether Hunch
  would say how it feels is decided by `shows_mood`; when it is masked, the prompt text says that
  Hunch keeps the feeling to itself, and the drive vector only gets `mask_leak` of the mood.
- All tunables live in config ([mood], [relationship], [mood_drive]); this module has none.

Everything except `MoodStore` is a pure function of its arguments (no clock, no RNG), so tests and
the simulation can replay any history. `MoodStore` persists the two states and keeps an
append-only `mood_log` for the admin (invariant 7); the AI never reads that log.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass

from hunch.config import MoodConfig, MoodDriveConfig, RelationshipConfig

SECONDS_PER_HOUR = 3600.0
SECONDS_PER_DAY = 86400.0


@dataclass(frozen=True, slots=True)
class Mood:
    valence: float
    arousal: float
    energy: float
    t: float  # unix seconds of this state


@dataclass(frozen=True, slots=True)
class Relationship:
    trust: float
    closeness: float
    hurt: float
    t: float  # unix seconds of this state


@dataclass(frozen=True, slots=True)
class Exchange:
    """What one user message says about the relationship (flags come from rules or the pipeline).

    non_negative: the message valence is not negative (no emotion cue counts as non-negative)
    disclosure: the message is in a sensitive category (the user confides)
    privacy_answer: the user answered a privacy question
    """

    hostile: bool = False
    apology: bool = False
    non_negative: bool = True
    disclosure: bool = False
    privacy_answer: bool = False


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return min(max(x, lo), hi)


def _decay(x: float, neutral: float, dt: float, half_life: float) -> float:
    """Exponential return to `neutral`; dt and half_life share a unit. dt <= 0 changes nothing."""
    if dt <= 0:
        return x
    return neutral + (x - neutral) * 0.5 ** (dt / half_life)


# --- global mood ----------------------------------------------------------------------------------


def neutral_mood(cfg: MoodConfig, t: float) -> Mood:
    return Mood(cfg.neutral_valence, cfg.neutral_arousal, cfg.neutral_energy, t)


def event_energy(valence: float, arousal: float) -> float:
    """Energy of an emotional event: arousal pushes it up, valence a little (joy energises, sadness
    drains). joy (0.8, 0.6) -> 0.75; tired (-0.3, 0.1) -> 0.225."""
    return _clip(0.5 + 0.5 * (arousal - 0.5) + 0.25 * valence)


def decay_mood(m: Mood, now: float, cfg: MoodConfig) -> Mood:
    """The mood at `now` if nothing happened since m.t. A `now` before m.t (clock skew): no-op."""
    if now <= m.t:
        return m
    dt = (now - m.t) / SECONDS_PER_HOUR
    hl = cfg.half_life_hours
    return Mood(
        _decay(m.valence, cfg.neutral_valence, dt, hl),
        _decay(m.arousal, cfg.neutral_arousal, dt, hl),
        _decay(m.energy, cfg.neutral_energy, dt, hl),
        now,
    )


def apply_mood_event(m: Mood, affect: tuple[float, float], now: float, cfg: MoodConfig) -> Mood:
    """Decay to `now`, then move event_rate of the way toward the event (valence, arousal,
    energy)."""
    m = decay_mood(m, now, cfg)
    ev_v = _clip(affect[0], -1.0, 1.0)
    ev_a = _clip(affect[1])
    ev_e = event_energy(ev_v, ev_a)
    k = cfg.event_rate
    return Mood(
        _clip(m.valence + k * (ev_v - m.valence), -1.0, 1.0),
        _clip(m.arousal + k * (ev_a - m.arousal)),
        _clip(m.energy + k * (ev_e - m.energy)),
        max(now, m.t),
    )


# --- relationship ---------------------------------------------------------------------------------


def start_relationship(cfg: RelationshipConfig, t: float) -> Relationship:
    return Relationship(cfg.trust_start, cfg.closeness_start, cfg.hurt_start, t)


def decay_relationship(r: Relationship, now: float, cfg: RelationshipConfig) -> Relationship:
    if now <= r.t:
        return r
    dt = (now - r.t) / SECONDS_PER_DAY
    return Relationship(
        _decay(r.trust, cfg.trust_start, dt, cfg.trust_half_life_days),
        _decay(r.closeness, cfg.closeness_start, dt, cfg.closeness_half_life_days),
        _decay(r.hurt, cfg.hurt_start, dt, cfg.hurt_half_life_days),
        now,
    )


def apply_exchange(
    r: Relationship, ex: Exchange, now: float, cfg: RelationshipConfig
) -> Relationship:
    """Decay to `now`, then apply one exchange. Order: hostility or friendliness, apology,
    closeness, confiding; everything is clipped to [0, 1] at the end.

    Berk (Phase 5, after the simulation): trust and closeness gains saturate, gain x (1 - value).
    With linear gains a regular user reached full trust in ~9 days and Hunch showed its mood to
    everyone after two weeks; now, at ~5 exchanges a day, they settle near 0.9 and 0.6 against
    the decay. Losses (hostility) and hurt stay linear."""
    r = decay_relationship(r, now, cfg)
    trust, closeness, hurt = r.trust, r.closeness, r.hurt
    if ex.hostile:
        trust -= cfg.trust_hostile
        hurt += cfg.hurt_hostile
    elif ex.non_negative:
        trust += cfg.trust_per_exchange * (1.0 - _clip(trust))
    if ex.apology:
        hurt *= cfg.apology_factor
    closeness += cfg.closeness_per_exchange * (1.0 - closeness)
    if ex.disclosure:
        closeness += cfg.closeness_disclosure * (1.0 - _clip(closeness))
    if ex.privacy_answer:
        trust += cfg.trust_privacy_answer * (1.0 - _clip(trust))
    return Relationship(_clip(trust), _clip(closeness), _clip(hurt), max(now, r.t))


# --- what leaves this module: label, prompt text, drive terms -------------------------------------


def mood_label(m: Mood, cfg: MoodConfig) -> str:
    """Coarse label of the mood; the only mood content that may enter a prompt (never numbers)."""
    if m.valence <= cfg.low_valence:
        base = "low"
    elif m.valence <= cfg.a_bit_low_valence:
        base = "a bit low"
    elif m.valence >= cfg.cheerful_valence:
        base = "cheerful"
    elif m.valence >= cfg.good_valence:
        base = "in a good mood"
    else:
        base = cfg.neutral_label
    modifiers: list[str] = []
    if m.arousal >= cfg.tense_arousal and m.valence < 0:
        modifiers.append("tense")
    if m.energy <= cfg.tired_energy:
        modifiers.append("tired")
    # A neutral base adds nothing next to a modifier: "tense", not "calm and tense".
    parts = modifiers if base == cfg.neutral_label and modifiers else [base, *modifiers]
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def shows_mood(asks_how: bool, r: Relationship, mcfg: MoodConfig, rcfg: RelationshipConfig) -> bool:
    """Show the mood when asked, to someone who hurt Hunch, or to someone close; else mask it."""
    return asks_how or r.hurt >= rcfg.hurt_label or r.closeness >= mcfg.show_closeness


def prompt_mood(
    m: Mood, r: Relationship, shown: bool, mcfg: MoodConfig, rcfg: RelationshipConfig
) -> str:
    """The text after "How you feel right now: " in the prompt. Words only, never numbers."""
    label = mood_label(m, mcfg)
    if shown or label == mcfg.neutral_label:
        text = label
    else:
        text = f"{label}, but you keep that to yourself in this conversation"
    if r.hurt >= rcfg.hurt_label:
        text += "; with this person you feel a little hurt"
    return text


def drive_terms(
    m: Mood,
    r: Relationship,
    shown: bool,
    mcfg: MoodConfig,
    rcfg: RelationshipConfig,
    dcfg: MoodDriveConfig,
) -> dict[str, float]:
    """Terms the caller adds to the drive vector (hunch.drive.compute_drive `extra`). The mood part
    is scaled by 1 when shown and by mask_leak when masked (the feeling leaks into behaviour a
    little even when Hunch keeps it to itself); the relationship part is never masked."""
    share = 1.0 if shown else mcfg.mask_leak
    v = m.valence - mcfg.neutral_valence
    e = m.energy - mcfg.neutral_energy
    return {
        "warmth": share * dcfg.warmth_mood * v
        + dcfg.warmth_closeness * (r.closeness - rcfg.closeness_start)
        - dcfg.warmth_hurt * r.hurt,
        "caution": -share * dcfg.caution_mood * v
        + dcfg.caution_trust * (rcfg.trust_start - r.trust)
        + dcfg.caution_hurt * r.hurt,
        "energy": share * dcfg.energy_mood * e,
        "curiosity": share * dcfg.curiosity_energy * e
        + dcfg.curiosity_closeness * (0.5 - r.closeness),
    }


def stress_factor(m: Mood, mcfg: MoodConfig) -> float:
    """Multiplier for the modulation weight: high arousal makes the drive count more, whether or
    not the mood is shown (stress is not something Hunch can hide from itself)."""
    return 1.0 + mcfg.stress_gain * max(0.0, 2.0 * (m.arousal - 0.5))


# --- persistence ----------------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS mood_state (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    valence REAL NOT NULL,
    arousal REAL NOT NULL,
    energy REAL NOT NULL,
    t REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS relationship_state (
    user TEXT PRIMARY KEY,
    trust REAL NOT NULL,
    closeness REAL NOT NULL,
    hurt REAL NOT NULL,
    t REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS mood_log (
    t REAL NOT NULL,
    scope TEXT NOT NULL,
    state TEXT NOT NULL,
    reason TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS mood_log_no_update BEFORE UPDATE ON mood_log
BEGIN SELECT RAISE(ABORT, 'mood_log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS mood_log_no_delete BEFORE DELETE ON mood_log
BEGIN SELECT RAISE(ABORT, 'mood_log is append-only'); END;
"""


class MoodStore:
    """Persists the global mood (one row) and one relationship per user; logs every save.

    Reads return the stored state decayed to `now`; saves write the state as given (the caller
    already decayed it via apply_*). `mood_log` is the admin's history of how and why the states
    moved; nothing in it ever reaches a model prompt.
    """

    def __init__(self, db: sqlite3.Connection, mcfg: MoodConfig, rcfg: RelationshipConfig) -> None:
        self._db = db
        self._mcfg = mcfg
        self._rcfg = rcfg
        with db:
            db.executescript(_SCHEMA)

    def mood(self, now: float) -> Mood:
        row = self._db.execute("SELECT valence, arousal, energy, t FROM mood_state WHERE id = 1")
        found = row.fetchone()
        if found is None:
            return neutral_mood(self._mcfg, now)
        return decay_mood(Mood(*found), now, self._mcfg)

    def relationship(self, user: str, now: float) -> Relationship:
        row = self._db.execute(
            "SELECT trust, closeness, hurt, t FROM relationship_state WHERE user = ?", (user,)
        )
        found = row.fetchone()
        if found is None:
            return start_relationship(self._rcfg, now)
        return decay_relationship(Relationship(*found), now, self._rcfg)

    def save_mood(self, m: Mood, reason: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO mood_state (id, valence, arousal, energy, t) VALUES (1, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET valence = excluded.valence, "
                "arousal = excluded.arousal, energy = excluded.energy, t = excluded.t",
                (m.valence, m.arousal, m.energy, m.t),
            )
            self._append("global", m.t, asdict(m), reason)

    def save_relationship(self, user: str, r: Relationship, reason: str) -> None:
        with self._db:
            self._db.execute(
                "INSERT INTO relationship_state (user, trust, closeness, hurt, t) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(user) DO UPDATE SET trust = excluded.trust, "
                "closeness = excluded.closeness, hurt = excluded.hurt, t = excluded.t",
                (user, r.trust, r.closeness, r.hurt, r.t),
            )
            self._append(f"user:{user}", r.t, asdict(r), reason)

    def _append(self, scope: str, t: float, state: dict[str, float], reason: str) -> None:
        self._db.execute(
            "INSERT INTO mood_log (t, scope, state, reason) VALUES (?, ?, ?, ?)",
            (t, scope, json.dumps(state, sort_keys=True), reason),
        )

    def log(self) -> list[dict[str, object]]:
        """Admin view of the history, oldest first. State is the decoded JSON."""
        rows = self._db.execute("SELECT t, scope, state, reason FROM mood_log ORDER BY rowid")
        return [
            {"t": t, "scope": scope, "state": json.loads(state), "reason": reason}
            for t, scope, state, reason in rows.fetchall()
        ]


__all__ = [
    "Exchange",
    "Mood",
    "MoodStore",
    "Relationship",
    "apply_exchange",
    "apply_mood_event",
    "decay_mood",
    "decay_relationship",
    "drive_terms",
    "event_energy",
    "mood_label",
    "neutral_mood",
    "prompt_mood",
    "shows_mood",
    "start_relationship",
    "stress_factor",
]
