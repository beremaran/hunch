"""Graded reflection (Phase 4): unlock chance, privacy caps, justified vs. unjustified, what a
reflection leaves behind, and determinism with the seeded RNG."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import numpy as np
import pytest

from hunch.memory.store import MemoryStore
from hunch.observability.turn_log import REFLECTIONS_FILE, ReflectionLog
from hunch.reflection.records import Hunch, SourceRef
from hunch.reflection.reflect import (
    Reflector,
    level_cap,
    realisation_clause,
    unlock_probability,
)
from tests.pipeline_support import DAY, NOW, seed_memory


class Draws:
    """An RNG stand-in that returns fixed draws."""

    def __init__(self, *values: float) -> None:
        self.values = list(values)

    def random(self) -> float:
        return self.values.pop(0)


def _hunch(store: MemoryStore, source: str, strength: float = 0.4, relevant: bool = True,
           user: str = "u_berk", level: int = 0) -> Hunch:  # fmt: skip
    ep = store.append_turn("c-now", user, "user", "Should I go to the harbour party?", at=NOW)
    h = Hunch(
        f"h-{ep.id[:8]}", user, "c-now", "c-now-t1", ep.id, {"place:harbour": 0.8}, NOW,
        -0.6, 0.4, (SourceRef(source, strength, relevant),), level,
    )  # fmt: skip
    store.add_hunch(h)
    return h


def _reflector(pipe_cfg, store, rng, tmp_path: Path | None = None) -> Reflector:
    log = ReflectionLog(tmp_path / "logs", tmp_path / "core") if tmp_path else None
    return Reflector(
        pipe_cfg.reflection, store, rng, lambda h: "a faint hunch, slightly negative",
        pipe_cfg.encoding, log, clock=lambda: NOW,
    )  # fmt: skip


def _source(store: MemoryStore, mid: str = "s1", owner: str = "u_berk", privacy: str = "private",
            valence: float = -0.8, age: float = 10) -> None:  # fmt: skip
    seed_memory(store, mid, 'They said: "Tom shouted at me at the harbour party."',
                {"person:tom": 1.0, "place:harbour": 0.7}, age, owner=owner, privacy=privacy,
                affect=(valence, 0.8), salience=0.7)  # fmt: skip


# --- unlock probability ---------------------------------------------------------------------------


def test_unlock_probability_matches_the_approved_formula(pipe_cfg) -> None:
    r = pipe_cfg.reflection
    # 0.5 x 1.0 x sqrt(0.3) / (1 + 1/90)
    assert unlock_probability(r, r.effort_ask, 1, 0.3, 1) == pytest.approx(0.2708, abs=1e-4)
    # level 3 is harder, older is harder, nightly is easier
    assert unlock_probability(r, r.effort_ask, 3, 0.3, 1) < unlock_probability(
        r, r.effort_ask, 1, 0.3, 1
    )
    assert unlock_probability(r, r.effort_ask, 1, 0.3, 180) < unlock_probability(
        r, r.effort_ask, 1, 0.3, 1
    )
    assert unlock_probability(r, r.effort_nightly, 1, 0.3, 1) > unlock_probability(
        r, r.effort_ask, 1, 0.3, 1
    )


def test_very_weak_traces_never_unlock_and_p_is_capped(pipe_cfg) -> None:
    r = pipe_cfg.reflection
    assert unlock_probability(r, 1.0, 1, 0.049, 0) == 0.0
    big = dataclasses.replace(r, effort_nightly=1.0, max_p=0.95, level_difficulty=(1, 1, 1))
    assert unlock_probability(big, 1.0, 1, 1.0, 0) == 0.95


# --- privacy caps ---------------------------------------------------------------------------------


def test_level_caps(pipe_store: MemoryStore) -> None:
    _source(pipe_store, "own")
    _source(pipe_store, "anna_private", owner="u_anna", privacy="private")
    _source(pipe_store, "anna_general", owner="u_anna", privacy="general")
    h = _hunch(pipe_store, "own")
    assert level_cap(h, pipe_store.memory("own")) == 3
    assert level_cap(h, pipe_store.memory("anna_private")) == 0  # Berk: never past the feeling
    assert level_cap(h, pipe_store.memory("anna_general")) == 3
    assert level_cap(h, None) == 0  # removed by an admin forget: nothing to reveal
    suppressed = dataclasses.replace(pipe_store.memory("own"), suppressed=True)
    assert level_cap(h, suppressed) == 0  # a user "forget" never reaches reasoning


def test_another_users_private_source_stays_at_level_zero(pipe_cfg, pipe_store) -> None:
    _source(pipe_store, "anna_private", owner="u_anna", privacy="private")
    out = _reflector(pipe_cfg, pipe_store, Draws(0.0, 0.0, 0.0)).reflect(
        _hunch(pipe_store, "anna_private"), "nightly"
    )
    assert out.hunch.revealed_level == 0 and not out.realisations
    assert [(a.p, a.draw) for a in out.attempts] == [(0.0, None)]


# --- levels and what they reveal ------------------------------------------------------------------


def test_one_level_per_attempt_and_nightly_stops_at_the_first_failure(pipe_cfg, pipe_store) -> None:
    _source(pipe_store)
    ref = _reflector(pipe_cfg, pipe_store, Draws(0.0))
    out = ref.reflect(_hunch(pipe_store, "s1"), "ask")
    assert (out.level_before, out.hunch.revealed_level) == (0, 1)
    assert pipe_store.hunch(out.hunch.id).revealed_level == 1

    ref.rng = Draws(0.0, 0.99, 0.0)  # level 2, then a failure: level 3 is not tried
    out = ref.reflect(pipe_store.hunch(out.hunch.id), "nightly")
    assert out.hunch.revealed_level == 2 and len(out.attempts) == 2
    assert [a.unlocked for a in out.attempts] == [True, False]


def test_each_level_reveals_only_itself(pipe_cfg, pipe_store) -> None:
    _source(pipe_store)
    h = _hunch(pipe_store, "s1")
    src = pipe_store.memory("s1")
    one = realisation_clause(h, src, 1, NOW, "u_berk")
    two = realisation_clause(h, src, 2, NOW, "u_berk")
    three = realisation_clause(h, src, 3, NOW, "u_berk")
    assert realisation_clause(h, src, 0, NOW, "u_berk") is None
    assert one == "it seemed to be about someone" and "tom" not in one.casefold()
    assert "Tom" in two and "harbour party" not in two
    assert "Tom shouted at me at the harbour party." in three


def test_realisation_memories_are_written_per_unlocked_level(pipe_cfg, pipe_store) -> None:
    _source(pipe_store)
    ref = _reflector(pipe_cfg, pipe_store, Draws(0.0, 0.0, 0.99))
    out = ref.reflect(_hunch(pipe_store, "s1"), "nightly")
    assert out.hunch.revealed_level == 2
    one, two = out.realisations
    assert one.kind == two.kind == "realisation" and one.privacy == "private"
    assert "about someone" in one.summary and "Tom" not in one.summary
    assert "Tom" in two.summary and "shouted" not in two.summary
    assert "person:tom" in two.cues and "person:tom" not in one.cues
    ref.store_realisations(out, None)
    assert {m.id for m in pipe_store.memories("u_berk")} >= {one.id, two.id}


# --- level 3: justified or not --------------------------------------------------------------------


def test_justified_source_becomes_a_belief(pipe_cfg, pipe_store) -> None:
    _source(pipe_store)
    # corroborated: another visible memory shares "person:tom", also negative
    seed_memory(pipe_store, "s2", 'They said: "Tom was rude again."', {"person:tom": 1.0}, 3,
                affect=(-0.5, 0.5), salience=0.4)  # fmt: skip
    out = _reflector(pipe_cfg, pipe_store, Draws(0.0)).reflect(
        _hunch(pipe_store, "s1", level=2), "ask"
    )
    assert out.hunch.revealed_level == 3 and out.hunch.verdict == "justified"
    (belief,) = pipe_store.beliefs("u_berk")
    assert belief.confidence == 0.6 and set(belief.evidence) == {"s1", "s2"}
    assert "fair" in out.realisations[-1].summary
    assert pipe_store.memory("s1").salience == 0.7  # not weakened


@pytest.mark.parametrize(
    ("relevant", "other_valence"),
    [(True, None), (True, 0.6), (False, -0.5)],  # alone; contradicted; not relevant
)
def test_unjustified_source_is_weakened(pipe_cfg, pipe_store, relevant, other_valence) -> None:
    _source(pipe_store)
    if other_valence is not None:
        seed_memory(pipe_store, "s2", 'They said: "Tom helped me move."', {"person:tom": 1.0}, 3,
                    affect=(other_valence, 0.5), salience=0.4)  # fmt: skip
    raw_before = pipe_store.episode(pipe_store.memory("s1").episode_ref)
    out = _reflector(pipe_cfg, pipe_store, Draws(0.0)).reflect(
        _hunch(pipe_store, "s1", relevant=relevant, level=2), "think_more"
    )
    assert out.hunch.verdict == "unjustified" and not pipe_store.beliefs()
    m = pipe_store.memory("s1")
    assert m.salience == pytest.approx(0.35) and m.affect[1] == pytest.approx(0.4)
    assert len(pipe_store.trace_history("s1")) == 1
    assert pipe_store.episode(m.episode_ref) == raw_before  # the raw record never changes
    assert "changed your mind" in out.realisations[-1].summary


# --- determinism and the admin log ----------------------------------------------------------------


def test_same_seed_same_outcome(pipe_cfg, tmp_path: Path) -> None:
    levels = []
    for _ in range(2):
        store = MemoryStore(":memory:", core_dir=tmp_path / "core", embedding_dim=16)
        _source(store)
        ref = _reflector(pipe_cfg, store, np.random.default_rng(7))
        h = _hunch(store, "s1", strength=0.6)
        levels.append([ref.reflect(h, "nightly").hunch.revealed_level])
        levels[-1] += [ref.reflect(store.hunch(h.id), "nightly").hunch.revealed_level]
        store.close()
    assert levels[0] == levels[1]


def test_reflection_log_has_the_admin_details(pipe_cfg, pipe_store, tmp_path: Path) -> None:
    _source(pipe_store, age=30)
    out = _reflector(pipe_cfg, pipe_store, Draws(0.0, 0.99), tmp_path).reflect(
        _hunch(pipe_store, "s1"), "nightly"
    )
    lines = (tmp_path / "logs" / REFLECTIONS_FILE).read_text().splitlines()
    (rec,) = [json.loads(x) for x in lines]
    assert rec["reflection_id"] == out.reflection_id and rec["hunch_id"] == out.hunch.id
    assert rec["source"]["memory"] == "s1" and rec["source"]["age_days"] == pytest.approx(30)
    assert [a["unlocked"] for a in rec["attempts"]] == [True, False]
    assert all(a["p"] > 0 for a in rec["attempts"]) and rec["level_after"] == 1


def test_nightly_hook_reviews_the_days_hunches(pipe_cfg, pipe_store) -> None:
    _source(pipe_store)
    h = _hunch(pipe_store, "s1")
    old = dataclasses.replace(h, id="h-old", created_at=NOW - 3 * DAY)
    pipe_store.add_hunch(old)
    outs = _reflector(pipe_cfg, pipe_store, Draws(0.0, 0.0, 0.0)).nightly(since=NOW - DAY)
    assert [o.hunch.id for o in outs] == [h.id]
    assert outs[0].hunch.revealed_level == 3
