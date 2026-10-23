"""Nightly step 6 (Phase 7): repeated experiences consolidate, repeats fade, never across users."""

from __future__ import annotations

import dataclasses

from hunch.consolidation.fade import merge_repeats, repeat_key
from hunch.memory.store import MemoryStore
from tests.pipeline_support import NOW, seed_memory


def test_repeat_key_ignores_case_and_punctuation() -> None:
    assert repeat_key('They said: "What folders can you access?"') == repeat_key(
        'They said: "what folders can you access"'
    )
    assert repeat_key('They said: "hey"') != repeat_key('They said: "hey you"')


def test_the_oldest_repeat_gains_and_the_rest_fade_once(pipe_store: MemoryStore, pipe_cfg):
    cfg = pipe_cfg.nightly
    text = 'They said: "my landlord still has not fixed the heating"'
    for i, age in enumerate((3, 2, 1)):
        seed_memory(pipe_store, f"f{i}", text, {}, age)
    seed_memory(pipe_store, "other", 'They said: "my sister moved to Lyon"', {}, 1)

    result = merge_repeats(pipe_store, cfg, NOW)

    assert (result.survivors, result.repeats) == (1, 2)
    assert pipe_store.memory("f0").salience == 0.2 + 2 * cfg.repeat_boost
    for mid in ("f1", "f2"):
        assert pipe_store.memory(mid).salience == 0.2 * cfg.filler_salience_factor
    assert pipe_store.memory("other").salience == 0.2
    again = merge_repeats(pipe_store, cfg, NOW + 60)
    assert (again.survivors, again.repeats) == (0, 0)
    assert pipe_store.memory("f0").salience == 0.2 + 2 * cfg.repeat_boost


def test_the_same_words_from_two_users_never_merge(pipe_store: MemoryStore, pipe_cfg) -> None:
    seed_memory(pipe_store, "a", 'They said: "hey"', {}, 2, owner="u_berk")
    seed_memory(pipe_store, "b", 'They said: "hey"', {}, 1, owner="u_lea")
    assert merge_repeats(pipe_store, pipe_cfg.nightly, NOW).repeats == 0


def test_a_suppressed_memory_is_left_alone(pipe_store: MemoryStore, pipe_cfg) -> None:
    seed_memory(pipe_store, "a", 'They said: "hey"', {}, 2)
    seed_memory(pipe_store, "b", 'They said: "hey"', {}, 1)
    pipe_store.db.execute("UPDATE memories SET suppressed = 1 WHERE id = 'b'")
    pipe_store.db.commit()
    assert merge_repeats(pipe_store, dataclasses.replace(pipe_cfg.nightly), NOW).repeats == 0


def test_a_repeated_routine_blurs_instead_of_growing_vivid(pipe_store, pipe_cfg) -> None:
    for i, age in enumerate((3, 2, 1)):
        seed_memory(pipe_store, f"h{i}", 'They said: "hey"', {}, age)
    assert merge_repeats(pipe_store, pipe_cfg.nightly, NOW).repeats == 2
    assert pipe_store.memory("h0").salience == 0.2
    assert pipe_store.memory("h1").salience < 0.2
