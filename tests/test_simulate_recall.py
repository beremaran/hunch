"""Regression: the 6-month recall simulation keeps its three properties with the config params."""

from __future__ import annotations

import pytest

from hunch.config import load_config
from scripts.simulate_recall import simulate


@pytest.fixture(scope="module")
def sim() -> dict:
    cfg = load_config()
    return simulate(cfg.activation, cfg.recall.max_upper_per_turn)


def test_some_memories_are_always_recalled_including_every_flashbulb(sim: dict) -> None:
    always = set(sim["checks"]["a_always_recalled"]["memories"])
    flashbulbs = {mid for mid, g in sim["groups"].items() if g == "flashbulb"}
    assert flashbulbs <= always, flashbulbs - always


def test_some_memories_only_come_back_with_a_rare_cue(sim: dict) -> None:
    assert sim["checks"]["b_only_rare_cue"]["memories"]


def test_rare_cue_beats_frequent_name(sim: dict) -> None:
    boosts = sim["checks"]["c_rare_beats_common"]["boosts"]
    assert boosts and all(b["song"] > b["name"] for b in boosts)


def test_most_everyday_memories_fade(sim: dict) -> None:
    always = set(sim["checks"]["a_always_recalled"]["memories"])
    everyday = {mid for mid, g in sim["groups"].items() if g == "everyday"}
    assert len(everyday & always) <= len(everyday) // 3


def test_simulation_is_deterministic() -> None:
    cfg = load_config()
    a = simulate(cfg.activation, cfg.recall.max_upper_per_turn)
    b = simulate(cfg.activation, cfg.recall.max_upper_per_turn)
    assert a["checks"] == b["checks"]
    assert a["access_log"] == b["access_log"]


def test_rehearsal_is_bounded(sim: dict) -> None:
    """Often-recalled memories do not keep climbing: never above their level right after creation
    (each recall makes them like a newly formed memory again)."""
    for mid, group in sim["groups"].items():
        trace = sim["traces"][mid]["common"]
        if group == "flashbulb" and trace:
            assert max(trace) <= trace[0] + 0.5, mid


def test_trivial_memories_do_not_lock_in(sim: dict) -> None:
    """e.g. 'Ben's heating broke' is recalled now and then but fades again; only emotionally strong
    memories (arousal x salience >= 0.3: flashbulbs, a new baby, a job interview) stay."""
    always = set(sim["checks"]["a_always_recalled"]["memories"])
    by_id = {m.id: m for m, _ in sim["items"]}
    recalled_trivial = [
        mid for mid, m in by_id.items() if m.affect[1] * m.salience < 0.3 and sim["access_log"][mid]
    ]
    assert recalled_trivial  # they do come back sometimes ...
    assert not set(recalled_trivial) & always  # ... but none stays for good
    assert all(by_id[mid].affect[1] * by_id[mid].salience >= 0.3 for mid in always)


def test_common_name_counts_in_context(sim: dict) -> None:
    """Berk: asked about the Anna you went sailing with, you remember it; Anna alone does not."""
    d = sim["checks"]["d_name_in_context"]
    assert d["pass"], d
    assert d["name_term"]["anna_in_sailing_context"] > 5 * d["name_term"]["anna_alone"] > 0
