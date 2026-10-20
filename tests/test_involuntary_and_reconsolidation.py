from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pytest

from hunch.config import load_config
from hunch.memory.schema import Memory
from hunch.memory.store import MemoryStore, StoreError
from hunch.recall.activation import ActivationBreakdown, ActivationParams
from hunch.recall.involuntary import (
    ScoredMemory,
    SessionRecallState,
    is_involuntary,
    select_involuntary,
)
from hunch.recall.reconsolidation import drift_affect, recall_memory

PARAMS = ActivationParams(
    decay_d=0.5, min_age_days=1 / 24, encoding_alpha=3.0, spreading_s=3.0, min_cue_strength=0.2,
    cue_type_weights=dict.fromkeys(("person", "place", "song", "film", "date", "emotion",
                                    "phrase"), 1.0),
    mood_mu=0.5, noise_s=0.0, tau_upper=-0.5, tau_lower=-1.5,
)  # fmt: skip


def _mem(mid: str, suppressed: bool = False) -> Memory:
    return Memory(
        mid, "u_anna", "general", "e1", f"summary {mid}", {"song:x": 1.0}, (0.5, 0.5), 0.5, 0.0,
        suppressed=suppressed,
    )  # fmt: skip


def _scored(mid: str, base: float, spreading: float, suppressed: bool = False) -> ScoredMemory:
    return ScoredMemory(_mem(mid, suppressed), ActivationBreakdown(base, 0.0, spreading, 0.0, 0.0))


# --- involuntary recall --------------------------------------------------------------------------


def test_cue_driven_memory_is_involuntary() -> None:
    assert is_involuntary(_scored("m1", base=-2.0, spreading=2.7), set(), PARAMS)


@pytest.mark.parametrize(
    ("scored", "deliberate", "why"),
    [
        (_scored("m1", -2.0, 2.7), {"m1"}, "retrieved on purpose"),
        (_scored("m1", 0.5, 2.7), set(), "would be above tau_upper without the cue"),
        (_scored("m1", -2.0, 1.0), set(), "still below tau_upper"),
        (_scored("m1", 0.5, 0.0), set(), "no cue involved"),
        (_scored("m1", -2.0, 2.7, suppressed=True), set(), "user asked to forget it"),
    ],
)
def test_not_involuntary(scored: ScoredMemory, deliberate: set[str], why: str) -> None:
    assert not is_involuntary(scored, deliberate, PARAMS), why


def test_session_cap_holds_across_turns() -> None:
    state = SessionRecallState()
    turn1 = [_scored("m1", -2.0, 2.7), _scored("m2", -2.0, 2.9)]
    turn2 = [_scored("m3", -2.0, 2.8)]
    picked = select_involuntary(turn1, set(), PARAMS, cap_per_session=1, state=state)
    assert [s.memory.id for s in picked] == ["m2"]  # the strongest
    assert select_involuntary(turn2, set(), PARAMS, cap_per_session=1, state=state) == []
    assert state.involuntary_used == 1


def test_sessions_are_independent() -> None:
    turn = [_scored("m1", -2.0, 2.7)]
    a, b = SessionRecallState(), SessionRecallState()
    assert select_involuntary(turn, set(), PARAMS, 1, a)
    assert select_involuntary(turn, set(), PARAMS, 1, b)


def test_cap_zero_disables_involuntary_recall() -> None:
    state = SessionRecallState()
    assert select_involuntary([_scored("m1", -2.0, 2.7)], set(), PARAMS, 0, state) == []


def test_repo_config_has_recall_params() -> None:
    cfg = load_config().recall
    assert cfg.involuntary_per_session >= 0
    assert 0 <= cfg.reconsolidation_rate <= 1


# --- reconsolidation -----------------------------------------------------------------------------


def test_drift_moves_toward_mood() -> None:
    assert drift_affect((-0.8, 0.9), (0.2, 0.4), 0.1) == pytest.approx((-0.7, 0.85))
    assert drift_affect((0.3, 0.3), (0.3, 0.3), 0.5) == pytest.approx((0.3, 0.3))
    assert drift_affect((-0.8, 0.9), (0.2, 0.4), 0.0) == pytest.approx((-0.8, 0.9))


def test_repeated_recalls_converge_but_never_overshoot() -> None:
    affect, mood = (-0.9, 0.9), (0.6, 0.2)
    for _ in range(200):
        new = drift_affect(affect, mood, 0.1)
        assert abs(new[0] - mood[0]) <= abs(affect[0] - mood[0])
        affect = new
    assert affect == pytest.approx(mood, abs=1e-6)


def test_drift_rate_is_validated() -> None:
    with pytest.raises(ValueError):
        drift_affect((0, 0.5), (0, 0.5), 1.5)


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    s = MemoryStore(tmp_path / "h.db", core_dir=tmp_path / "core", embedding_dim=2)
    yield s
    s.close()


def test_recall_drifts_the_memory_but_never_the_raw_record(store: MemoryStore) -> None:
    ep = store.append_turn("c1", "u_anna", "user", "The day of the car accident.", at=0.0)
    m = Memory("m1", "u_anna", "general", ep.id, "car accident", {"place:motorway": 0.8},
               (-0.9, 0.9), 0.9, 0.0)  # fmt: skip
    store.add_memory(m, np.array([1.0, 0.0]))

    for i in range(3):
        recall_memory(store, "m1", mood=(0.5, 0.3), rate=0.1, at=100.0 + i)

    now = store.memory("m1")
    assert now.affect[0] > -0.9 and now.affect[1] < 0.9  # drifted toward the calm, happy mood
    assert now.access_times == (100.0, 101.0, 102.0)  # each recall is also a rehearsal
    history = store.affect_history("m1")
    assert [r for *_, r in history] == ["encoded"] + ["reconsolidation"] * 3
    assert history[0][1:3] == (-0.9, 0.9)  # the original encoding stays known
    assert store.episode(ep.id).text == "The day of the car accident."  # raw log untouched


def test_affect_log_is_append_only(store: MemoryStore) -> None:
    ep = store.append_turn("c1", "u_anna", "user", "x")
    store.add_memory(Memory("m1", "u", "general", ep.id, "s", {}, (0, 0.5), 0.5, 0.0),
                     np.array([1.0, 0.0]))  # fmt: skip
    for sql in ("UPDATE memory_affect_log SET valence = 1", "DELETE FROM memory_affect_log"):
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            store.db.execute(sql)


def test_update_affect_validates(store: MemoryStore) -> None:
    with pytest.raises(StoreError):
        store.update_affect("m1", (2.0, 0.5), reason="x")
    with pytest.raises(KeyError):
        store.update_affect("missing", (0.0, 0.5), reason="x")
