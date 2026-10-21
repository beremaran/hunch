from __future__ import annotations

import re
import sqlite3
from dataclasses import replace

import pytest

from hunch.config import load_config
from hunch.mood.state import (
    SECONDS_PER_DAY,
    SECONDS_PER_HOUR,
    Exchange,
    Mood,
    MoodStore,
    Relationship,
    apply_exchange,
    apply_mood_event,
    decay_mood,
    decay_relationship,
    drive_terms,
    event_energy,
    mood_label,
    neutral_mood,
    prompt_mood,
    shows_mood,
    start_relationship,
    stress_factor,
)

CFG = load_config()
M = CFG.mood
R = CFG.relationship
D = CFG.mood_drive
HOUR = SECONDS_PER_HOUR
DAY = SECONDS_PER_DAY


def mood(valence: float = 0.0, arousal: float = 0.5, energy: float = 0.5, t: float = 0.0) -> Mood:
    return Mood(valence, arousal, energy, t)


def rel(trust: float | None = None, closeness: float | None = None, hurt: float | None = None):
    base = start_relationship(R, 0.0)
    return replace(
        base,
        trust=base.trust if trust is None else trust,
        closeness=base.closeness if closeness is None else closeness,
        hurt=base.hurt if hurt is None else hurt,
    )


# --- global mood ----------------------------------------------------------------------------------


def test_event_energy_examples() -> None:
    assert event_energy(0.8, 0.6) == pytest.approx(0.75)  # joy
    assert event_energy(-0.3, 0.1) == pytest.approx(0.225)  # tired
    assert event_energy(0.0, 0.5) == pytest.approx(0.5)
    assert event_energy(1.0, 1.0) == 1.0  # clipped
    assert event_energy(-1.0, 0.0) == 0.0


def test_decay_halves_the_distance_to_neutral_per_half_life() -> None:
    m = mood(0.8, 0.9, 0.1)
    out = decay_mood(m, m.t + M.half_life_hours * HOUR, M)
    assert out.valence == pytest.approx(M.neutral_valence + 0.4)
    assert out.arousal == pytest.approx(M.neutral_arousal + 0.2)
    assert out.energy == pytest.approx(M.neutral_energy - 0.2)
    assert out.t == m.t + M.half_life_hours * HOUR
    twice = decay_mood(m, m.t + 2 * M.half_life_hours * HOUR, M)
    assert twice.valence == pytest.approx(M.neutral_valence + 0.2)


def test_decay_is_composable_and_never_overshoots() -> None:
    m = mood(-0.6, 0.8, 0.2)
    direct = decay_mood(m, 7 * HOUR, M)
    stepwise = decay_mood(decay_mood(m, 2 * HOUR, M), 7 * HOUR, M)
    assert stepwise.valence == pytest.approx(direct.valence)
    assert stepwise.energy == pytest.approx(direct.energy)
    far = decay_mood(m, 1000 * HOUR, M)
    assert far.valence == pytest.approx(M.neutral_valence, abs=1e-9)
    assert far.energy == pytest.approx(M.neutral_energy, abs=1e-9)


def test_decay_to_a_time_before_the_state_is_a_noop() -> None:
    m = mood(0.5, t=100.0)
    assert decay_mood(m, 50.0, M) == m


def test_event_moves_event_rate_of_the_way_toward_the_event() -> None:
    out = apply_mood_event(neutral_mood(M, 0.0), (-0.7, 0.9), 0.0, M)
    assert out.valence == pytest.approx(M.event_rate * -0.7)
    assert out.arousal == pytest.approx(0.5 + M.event_rate * 0.4)
    assert out.energy == pytest.approx(0.5 + M.event_rate * (event_energy(-0.7, 0.9) - 0.5))
    assert out.t == 0.0


def test_event_decays_to_now_before_it_updates() -> None:
    m = mood(0.8)
    now = M.half_life_hours * HOUR
    out = apply_mood_event(m, (0.0, 0.5), now, M)
    # 0.8 decays to 0.4; the event (valence 0) pulls it down by event_rate
    assert out.valence == pytest.approx(0.4 * (1 - M.event_rate))
    assert out.t == now


def test_repeated_events_converge_toward_the_event_and_stay_in_range() -> None:
    m = neutral_mood(M, 0.0)
    for i in range(60):
        m = apply_mood_event(m, (-1.0, 1.0), float(i), M)
    assert -1.0 <= m.valence < -0.99
    assert 0.0 <= m.arousal <= 1.0 and 0.0 <= m.energy <= 1.0


# --- label ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("valence", "expected"),
    [
        (-1.0, "low"),
        (M.low_valence, "low"),
        (M.low_valence + 0.01, "a bit low"),
        (M.a_bit_low_valence, "a bit low"),
        (M.a_bit_low_valence + 0.01, M.neutral_label),
        (0.0, M.neutral_label),
        (M.good_valence - 0.01, M.neutral_label),
        (M.good_valence, "in a good mood"),
        (M.cheerful_valence - 0.01, "in a good mood"),
        (M.cheerful_valence, "cheerful"),
        (1.0, "cheerful"),
    ],
)
def test_label_buckets(valence: float, expected: str) -> None:
    assert mood_label(mood(valence), M) == expected


def test_label_combinations() -> None:
    tense, tired = M.tense_arousal, M.tired_energy
    assert mood_label(mood(-0.3, tense), M) == "a bit low and tense"
    assert mood_label(mood(-0.8, tense, tired), M) == "low, tense and tired"
    assert mood_label(mood(-0.8, 0.5, tired), M) == "low and tired"
    assert mood_label(mood(-0.1, tense), M) == "tense"  # neutral base: modifiers only
    assert mood_label(mood(-0.1, tense, tired), M) == "tense and tired"
    assert mood_label(mood(0.0, 0.5, tired), M) == "tired"
    assert mood_label(mood(0.6, 0.5, tired), M) == "cheerful and tired"
    assert mood_label(mood(0.3, 0.5, 0.9), M) == "in a good mood"


def test_tense_needs_negative_valence() -> None:
    assert mood_label(mood(0.6, 0.95), M) == "cheerful"
    assert mood_label(mood(0.0, 0.95), M) == M.neutral_label
    assert mood_label(mood(-0.01, 0.95), M) == "tense"


# --- show or mask and the prompt text -------------------------------------------------------------


def test_shows_mood_rule() -> None:
    assert not shows_mood(False, rel(), M, R)
    assert shows_mood(True, rel(), M, R)  # asked
    assert shows_mood(False, rel(hurt=R.hurt_label), M, R)  # hurt by this user
    assert not shows_mood(False, rel(hurt=R.hurt_label - 0.01), M, R)
    assert shows_mood(False, rel(closeness=M.show_closeness), M, R)  # close
    assert not shows_mood(False, rel(closeness=M.show_closeness - 0.01), M, R)


def test_prompt_text_shown_masked_and_hurt() -> None:
    low = mood(-0.8)
    calm = mood(0.0)
    assert prompt_mood(low, rel(), True, M, R) == "low"
    assert (
        prompt_mood(low, rel(), False, M, R)
        == "low, but you keep that to yourself in this conversation"
    )
    assert prompt_mood(calm, rel(), False, M, R) == M.neutral_label
    assert prompt_mood(calm, rel(), True, M, R) == M.neutral_label
    hurt = rel(hurt=R.hurt_label)
    assert (
        prompt_mood(calm, hurt, True, M, R)
        == f"{M.neutral_label}; with this person you feel a little hurt"
    )
    assert prompt_mood(low, hurt, False, M, R).endswith("; with this person you feel a little hurt")
    assert "hurt" not in prompt_mood(low, rel(hurt=R.hurt_label - 0.01), True, M, R)


def test_prompt_text_never_contains_digits() -> None:
    for v in (-1.0, -0.6, -0.3, 0.0, 0.3, 0.6, 1.0):
        for a in (0.0, 0.5, 0.9):
            for e in (0.1, 0.5, 0.9):
                for hurt in (0.0, 0.5):
                    for shown in (True, False):
                        text = prompt_mood(mood(v, a, e), rel(hurt=hurt), shown, M, R)
                        assert not re.search(r"\d", text), text


# --- drive terms and stress -----------------------------------------------------------------------


def test_neutral_mood_and_start_relationship_give_only_the_curiosity_baseline() -> None:
    for shown in (True, False):
        terms = drive_terms(neutral_mood(M, 0.0), start_relationship(R, 0.0), shown, M, R, D)
        assert set(terms) == {"warmth", "caution", "energy", "curiosity"}
        assert terms["warmth"] == pytest.approx(0.0)
        assert terms["caution"] == pytest.approx(0.0)
        assert terms["energy"] == pytest.approx(0.0)
        assert terms["curiosity"] == pytest.approx(
            D.curiosity_closeness * (0.5 - R.closeness_start)
        )


def test_drive_terms_formulas_when_shown() -> None:
    m = mood(0.6, 0.5, 0.8)
    r = rel(trust=0.7, closeness=0.5, hurt=0.1)
    t = drive_terms(m, r, True, M, R, D)
    assert t["warmth"] == pytest.approx(
        D.warmth_mood * 0.6 + D.warmth_closeness * (0.5 - R.closeness_start) - D.warmth_hurt * 0.1
    )
    assert t["caution"] == pytest.approx(
        -D.caution_mood * 0.6 + D.caution_trust * (R.trust_start - 0.7) + D.caution_hurt * 0.1
    )
    assert t["energy"] == pytest.approx(D.energy_mood * 0.3)
    assert t["curiosity"] == pytest.approx(D.curiosity_energy * 0.3 + D.curiosity_closeness * 0.0)


def test_masking_scales_only_the_mood_part_by_mask_leak() -> None:
    m = mood(-0.7, 0.8, 0.2)
    r = start_relationship(R, 0.0)  # relationship part is zero except the curiosity baseline
    shown = drive_terms(m, r, True, M, R, D)
    masked = drive_terms(m, r, False, M, R, D)
    base = D.curiosity_closeness * (0.5 - R.closeness_start)
    for key in ("warmth", "caution", "energy"):
        assert masked[key] == pytest.approx(M.mask_leak * shown[key])
    assert masked["curiosity"] - base == pytest.approx(M.mask_leak * (shown["curiosity"] - base))
    assert abs(masked["warmth"]) < abs(shown["warmth"])


def test_relationship_part_is_not_masked() -> None:
    m = neutral_mood(M, 0.0)
    r = rel(trust=0.2, closeness=0.4, hurt=0.5)
    assert drive_terms(m, r, True, M, R, D) == drive_terms(m, r, False, M, R, D)
    t = drive_terms(m, r, False, M, R, D)
    assert t["caution"] > 0  # lower trust and hurt make Hunch more careful
    assert t["warmth"] < 0  # hurt outweighs the closeness gain here


def test_stress_factor() -> None:
    assert stress_factor(mood(arousal=0.5), M) == 1.0
    assert stress_factor(mood(arousal=0.2), M) == 1.0  # calm does not lower the weight
    assert stress_factor(mood(arousal=1.0), M) == pytest.approx(1.0 + M.stress_gain)
    assert stress_factor(mood(arousal=0.75), M) == pytest.approx(1.0 + M.stress_gain * 0.5)


# --- relationship ---------------------------------------------------------------------------------


def test_relationship_decay_uses_each_half_life() -> None:
    r = Relationship(0.9, 0.8, 0.8, 0.0)
    out = decay_relationship(r, R.hurt_half_life_days * DAY, R)
    assert out.hurt == pytest.approx(R.hurt_start + 0.4)  # hurt: one half-life
    assert out.closeness > R.closeness_start + 0.5  # closeness: much slower
    assert out.trust > 0.8  # trust: slower still
    far = decay_relationship(r, 100000 * DAY, R)
    assert (far.trust, far.closeness, far.hurt) == pytest.approx(
        (R.trust_start, R.closeness_start, R.hurt_start)
    )


def test_hostile_message_lowers_trust_and_raises_hurt() -> None:
    r0 = start_relationship(R, 0.0)
    r1 = apply_exchange(r0, Exchange(hostile=True, non_negative=False), 0.0, R)
    assert r1.trust == pytest.approx(R.trust_start - R.trust_hostile)
    assert r1.hurt == pytest.approx(R.hurt_start + R.hurt_hostile)
    gain = R.closeness_per_exchange * (1 - R.closeness_start)
    assert r1.closeness == pytest.approx(R.closeness_start + gain)
    r3 = r1
    for _ in range(2):
        r3 = apply_exchange(r3, Exchange(hostile=True, non_negative=False), 0.0, R)
    assert r3.hurt > R.hurt_label and r3.trust < r1.trust


def test_hostile_takes_precedence_over_the_friendly_trust_gain() -> None:
    r = apply_exchange(start_relationship(R, 0.0), Exchange(hostile=True, non_negative=True), 0, R)
    assert r.trust == pytest.approx(R.trust_start - R.trust_hostile)


def test_friendly_exchange_builds_trust_and_closeness() -> None:
    r = apply_exchange(start_relationship(R, 0.0), Exchange(), 0.0, R)
    assert r.trust == pytest.approx(R.trust_start + R.trust_per_exchange * (1 - R.trust_start))
    gain = R.closeness_per_exchange * (1 - R.closeness_start)
    assert r.closeness == pytest.approx(R.closeness_start + gain)
    assert r.hurt == R.hurt_start


def test_negative_valence_message_adds_no_trust() -> None:
    r = apply_exchange(start_relationship(R, 0.0), Exchange(non_negative=False), 0.0, R)
    assert r.trust == R.trust_start


def test_disclosure_and_privacy_answer() -> None:
    r = apply_exchange(
        start_relationship(R, 0.0), Exchange(disclosure=True, privacy_answer=True), 0.0, R
    )
    c = R.closeness_start + R.closeness_per_exchange * (1 - R.closeness_start)
    assert r.closeness == pytest.approx(c + R.closeness_disclosure * (1 - c))
    t = R.trust_start + R.trust_per_exchange * (1 - R.trust_start)
    assert r.trust == pytest.approx(t + R.trust_privacy_answer * (1 - t))


def test_gains_saturate_below_one() -> None:
    # Berk (Phase 5): many friendly exchanges approach 1 ever more slowly, never jump past it.
    r = rel(trust=0.95, closeness=0.95)
    out = apply_exchange(r, Exchange(disclosure=True), 0.0, R)
    assert out.trust - 0.95 == pytest.approx(R.trust_per_exchange * 0.05)
    assert out.closeness < 0.96


def test_apology_scales_hurt_by_apology_factor() -> None:
    r = rel(hurt=0.6)
    out = apply_exchange(r, Exchange(apology=True), 0.0, R)
    assert out.hurt == pytest.approx(0.6 * R.apology_factor)
    assert R.apology_factor == 0.5  # the spec's "halves"; guards a config drift in this test


def test_exchange_decays_to_now_first() -> None:
    r = Relationship(0.5, 0.2, 0.8, 0.0)
    out = apply_exchange(r, Exchange(), R.hurt_half_life_days * DAY, R)
    assert out.hurt == pytest.approx(0.4)
    assert out.t == R.hurt_half_life_days * DAY


def test_values_are_clipped_to_unit_interval() -> None:
    r = rel(trust=0.05, closeness=0.99, hurt=0.9)
    out = apply_exchange(r, Exchange(hostile=True, disclosure=True), 0.0, R)
    assert out.trust == 0.0
    assert out.hurt == 1.0
    assert 0.99 < out.closeness < 1.0  # saturating gains approach 1, never pass it


def test_hurt_from_three_hostile_messages_falls_below_the_label_within_two_weeks() -> None:
    r = start_relationship(R, 0.0)
    for _ in range(3):
        r = apply_exchange(r, Exchange(hostile=True, non_negative=False), 0.0, R)
    assert r.hurt == pytest.approx(0.9)
    assert decay_relationship(r, 5 * DAY, R).hurt >= R.hurt_label  # still hurt after 5 days
    assert decay_relationship(r, 14 * DAY, R).hurt < R.hurt_label


# --- persistence ----------------------------------------------------------------------------------


@pytest.fixture
def db() -> sqlite3.Connection:
    return sqlite3.connect(":memory:")


def test_store_defaults_when_empty(db: sqlite3.Connection) -> None:
    store = MoodStore(db, M, R)
    assert store.mood(123.0) == neutral_mood(M, 123.0)
    assert store.relationship("u1", 123.0) == start_relationship(R, 123.0)
    assert store.log() == []


def test_store_round_trip_and_decay_across_reload(db: sqlite3.Connection) -> None:
    store = MoodStore(db, M, R)
    m = apply_mood_event(neutral_mood(M, 0.0), (-0.7, 0.9), 0.0, M)
    store.save_mood(m, "anger event")
    r = apply_exchange(start_relationship(R, 0.0), Exchange(hostile=True), 0.0, R)
    store.save_relationship("alice", r, "hostile")
    # a fresh store on the same connection reads the same state, decayed to the requested time
    reloaded = MoodStore(db, M, R)
    assert reloaded.mood(0.0) == m
    assert reloaded.relationship("alice", 0.0) == r
    later = M.half_life_hours * HOUR
    assert reloaded.mood(later).valence == pytest.approx(m.valence * 0.5)
    assert reloaded.mood(later) == decay_mood(m, later, M)
    day = R.hurt_half_life_days * DAY
    assert reloaded.relationship("alice", day).hurt == pytest.approx(r.hurt * 0.5)
    assert reloaded.relationship("bob", day) == start_relationship(R, day)  # other users unaffected


def test_store_upserts_one_row_per_scope(db: sqlite3.Connection) -> None:
    store = MoodStore(db, M, R)
    store.save_mood(mood(0.1, t=1.0), "a")
    store.save_mood(mood(0.2, t=2.0), "b")
    store.save_relationship("u", rel(trust=0.6), "c")
    store.save_relationship("u", rel(trust=0.7), "d")
    assert db.execute("SELECT COUNT(*) FROM mood_state").fetchone() == (1,)
    assert db.execute("SELECT COUNT(*) FROM relationship_state").fetchone() == (1,)
    assert store.mood(2.0).valence == pytest.approx(0.2)
    assert store.relationship("u", 0.0).trust == pytest.approx(0.7)


def test_mood_log_records_every_save_oldest_first(db: sqlite3.Connection) -> None:
    store = MoodStore(db, M, R)
    store.save_mood(mood(0.1, t=1.0), "first")
    store.save_relationship("alice", Relationship(0.4, 0.3, 0.3, 2.0), "second")
    store.save_mood(mood(0.2, t=3.0), "third")
    log = store.log()
    assert [row["reason"] for row in log] == ["first", "second", "third"]
    assert [row["scope"] for row in log] == ["global", "user:alice", "global"]
    assert [row["t"] for row in log] == [1.0, 2.0, 3.0]
    assert log[1]["state"] == {"trust": 0.4, "closeness": 0.3, "hurt": 0.3, "t": 2.0}
    assert log[0]["state"]["valence"] == 0.1


def test_mood_log_is_append_only(db: sqlite3.Connection) -> None:
    store = MoodStore(db, M, R)
    store.save_mood(mood(0.1, t=1.0), "x")
    with pytest.raises(sqlite3.DatabaseError):
        db.execute("UPDATE mood_log SET reason = 'edited'")
    with pytest.raises(sqlite3.DatabaseError):
        db.execute("DELETE FROM mood_log")
    assert [row["reason"] for row in store.log()] == ["x"]


def test_store_is_idempotent_on_the_same_database(db: sqlite3.Connection) -> None:
    MoodStore(db, M, R).save_mood(mood(0.3, t=5.0), "x")
    again = MoodStore(db, M, R)  # IF NOT EXISTS: must not wipe or fail
    assert again.mood(5.0).valence == pytest.approx(0.3)
    assert len(again.log()) == 1
