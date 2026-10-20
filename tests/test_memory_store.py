from __future__ import annotations

import itertools
import sqlite3
from pathlib import Path

import numpy as np
import pytest

from hunch.config import load_config
from hunch.memory.schema import Episode, Memory
from hunch.memory.store import MemoryStore, StoreError, group_exchanges, select_working_memory

DIM = 4


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    ids = (f"id{i:04d}" for i in itertools.count())
    clock = itertools.count(1_000_000, 60)
    s = MemoryStore(
        tmp_path / "data" / "hunch.db",
        core_dir=tmp_path / "core",
        embedding_dim=DIM,
        clock=lambda: float(next(clock)),
        new_id=lambda: next(ids),
    )
    yield s
    s.close()


def _memory(mid: str, episode: str, owner: str = "u_anna", **kw) -> Memory:
    base = {
        "id": mid,
        "owner_user": owner,
        "privacy": "general",
        "episode_ref": episode,
        "summary": f"summary {mid}",
        "cues": {"person:anna": 0.8},
        "affect": (0.2, 0.4),
        "salience": 0.5,
        "created_at": 1_000_000.0,
    }
    return Memory(**{**base, **kw})


def _vec(*xs: float) -> np.ndarray:
    v = np.array(xs, dtype=np.float32)
    return v / np.linalg.norm(v)


# --- raw turns -----------------------------------------------------------------------------------


def test_turns_are_numbered_per_conversation(store: MemoryStore) -> None:
    a0 = store.append_turn("c1", "u_anna", "user", "hi")
    a1 = store.append_turn("c1", "u_anna", "assistant", "hey!")
    b0 = store.append_turn("c2", "u_ben", "user", "hello")
    assert (a0.turn_index, a1.turn_index, b0.turn_index) == (0, 1, 0)
    assert [t.text for t in store.turns("c1")] == ["hi", "hey!"]
    assert [t.text for t in store.turns("c1", limit=1)] == ["hey!"]
    assert store.episode(a0.id) == a0


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE episodes SET text = 'rewritten'",
        "DELETE FROM episodes",
        "UPDATE memory_access SET t = 0",
        "DELETE FROM memory_access",
    ],
)
def test_raw_log_and_access_log_are_append_only(store: MemoryStore, sql: str) -> None:
    ep = store.append_turn("c1", "u_anna", "user", "my sister is moving")
    store.add_memory(_memory("m1", ep.id), _vec(1, 0, 0, 0))
    store.record_access("m1")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        store.db.execute(sql)
    assert store.episode(ep.id).text == "my sister is moving"
    assert len(store.memory("m1").access_times) == 1


def test_append_only_survives_reopen(tmp_path: Path) -> None:
    path = tmp_path / "hunch.db"
    s = MemoryStore(path, core_dir=tmp_path / "core", embedding_dim=DIM)
    s.append_turn("c1", "u", "user", "x")
    s.close()
    raw = sqlite3.connect(path)
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        raw.execute("DELETE FROM episodes")
    raw.close()


# --- memories ------------------------------------------------------------------------------------


def test_memory_round_trip(store: MemoryStore) -> None:
    ep = store.append_turn("c1", "u_anna", "user", "we danced to Hallelujah")
    m = _memory(
        "m1",
        ep.id,
        privacy="private",
        cues={"person:anna": 0.7, "song:hallelujah": 0.9},
        access_times=(1_000_100.0,),
    )
    store.add_memory(m, _vec(1, 0, 0, 0))
    assert store.memory("m1") == m


def test_record_access_appends(store: MemoryStore) -> None:
    ep = store.append_turn("c1", "u_anna", "user", "x")
    store.add_memory(_memory("m1", ep.id), _vec(1, 0, 0, 0))
    store.record_access("m1", at=2_000_000.0)
    store.record_access("m1", at=3_000_000.0)
    assert store.memory("m1").access_times == (2_000_000.0, 3_000_000.0)


def test_memory_needs_owner_and_valid_privacy(store: MemoryStore) -> None:
    with pytest.raises(ValueError, match="privacy"):
        _memory("m1", "e", privacy="secret")
    with pytest.raises(ValueError, match="owner_user"):
        _memory("m1", "e", owner="")
    ep = store.append_turn("c1", "u_anna", "user", "x")
    with pytest.raises(sqlite3.IntegrityError):
        store.db.execute(
            "INSERT INTO memories (id, owner_user, privacy, episode_ref, summary, valence, arousal,"
            " salience, created_at) VALUES ('m9', 'u', 'secret', ?, 's', 0, 0, 0, 0)",
            (ep.id,),
        )


def test_memory_must_reference_an_existing_episode(store: MemoryStore) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        store.add_memory(_memory("m1", "no-such-episode"), _vec(1, 0, 0, 0))


@pytest.mark.parametrize(
    "kw",
    [
        {"affect": (1.5, 0.5)},
        {"affect": (0.0, -0.1)},
        {"salience": 1.2},
        {"cues": {"anna": 0.5}},
        {"cues": {"smell:rain": 0.5}},
        {"cues": {"person:anna": 1.5}},
    ],
)
def test_memory_validates_lower_trace(kw: dict) -> None:
    with pytest.raises(ValueError):
        _memory("m1", "e", **kw)


def test_cue_fan_counts_memories_sharing_a_cue(store: MemoryStore) -> None:
    ep = store.append_turn("c1", "u_anna", "user", "x")
    for i in range(3):
        cues = {"person:anna": 0.5} | ({"song:hallelujah": 0.9} if i == 0 else {})
        store.add_memory(_memory(f"m{i}", ep.id, cues=cues), _vec(1, i, 0, 0))
    assert store.cue_fan("person:anna") == 3
    assert store.cue_fan("song:hallelujah") == 1
    assert store.cue_fan("song:unknown") == 0


def test_cue_fan_in_context(store: MemoryStore) -> None:
    ep = store.append_turn("c1", "u_anna", "user", "x")
    cue_sets = [
        {"person:anna": 0.5, "phrase:sailing": 0.8},
        {"person:anna": 0.5},
        {"person:anna": 0.5, "phrase:sailing": 0.5, "place:lake": 0.6},
    ]
    for i, cues in enumerate(cue_sets):
        store.add_memory(_memory(f"m{i}", ep.id, cues=cues), _vec(1, i, 0, 0))
    assert store.cue_fan("person:anna", frozenset({"phrase:sailing"})) == 2
    assert store.cue_fan("person:anna", frozenset({"place:lake", "phrase:sailing"})) == 2
    assert store.cue_fan("person:anna", frozenset({"place:lake"})) == 1


def test_similar_returns_nearest_and_filters_by_owner(store: MemoryStore) -> None:
    ep = store.append_turn("c1", "u_anna", "user", "x")
    store.add_memory(_memory("near", ep.id), _vec(1, 0.1, 0, 0))
    store.add_memory(_memory("far", ep.id), _vec(0, 0, 1, 0))
    store.add_memory(_memory("ben", ep.id, owner="u_ben"), _vec(1, 0, 0, 0))
    hits = store.similar(_vec(1, 0, 0, 0), k=2)
    assert [m.id for m, _ in hits] == ["ben", "near"]
    hits = store.similar(_vec(1, 0, 0, 0), k=1, owner_user="u_anna")
    assert [m.id for m, _ in hits] == ["near"]


def test_embedding_dimension_is_checked(store: MemoryStore) -> None:
    ep = store.append_turn("c1", "u_anna", "user", "x")
    with pytest.raises(StoreError, match="shape"):
        store.add_memory(_memory("m1", ep.id), np.ones(DIM + 1))


# --- where the database may live -----------------------------------------------------------------


@pytest.mark.parametrize("rel", ["core/hunch.db", "core/sub/hunch.db"])
def test_store_refuses_core_dir(tmp_path: Path, rel: str) -> None:
    with pytest.raises(StoreError, match="core"):
        MemoryStore(tmp_path / rel, core_dir=tmp_path / "core", embedding_dim=DIM)


@pytest.mark.parametrize("name", [".env", "values.yaml", "hunch.txt"])
def test_store_only_opens_database_files(tmp_path: Path, name: str) -> None:
    with pytest.raises(StoreError, match="must end in"):
        MemoryStore(tmp_path / name, core_dir=tmp_path / "core", embedding_dim=DIM)
    assert not (tmp_path / name).exists()


# --- working memory window -----------------------------------------------------------------------


def _turns(texts: list[str]) -> list[Episode]:
    return [
        Episode(f"e{i}", "c1", i, "u", "user" if i % 2 == 0 else "assistant", t, float(i))
        for i, t in enumerate(texts)
    ]


def words(text: str) -> int:
    return len(text.split())


def test_working_memory_counts_exchanges_as_turns() -> None:
    turns = _turns([f"message {i}" for i in range(28)])  # 14 exchanges (user + reply)
    window = select_working_memory(turns, max_turns=10, max_tokens=2000, count_tokens=words)
    assert [t.turn_index for t in window.verbatim] == list(range(8, 28))
    assert [t.turn_index for t in window.to_summarize] == list(range(8))


def test_group_exchanges_keeps_a_proactive_opener_apart() -> None:
    eps = [
        Episode("e0", "c1", 0, "u", "assistant", "hi, how did the run go?", 0.0),
        Episode("e1", "c1", 1, "u", "user", "great", 1.0),
        Episode("e2", "c1", 2, "u", "assistant", "nice", 2.0),
        Episode("e3", "c1", 3, "u", "user", "and you?", 3.0),
    ]
    assert [[e.turn_index for e in x] for x in group_exchanges(eps)] == [[0], [1, 2], [3]]


def test_working_memory_caps_tokens_and_folds_oldest() -> None:
    turns = _turns(["a " * 800, "b " * 800, "c " * 800])  # exchanges [0, 1] and [2]
    window = select_working_memory(turns, max_turns=10, max_tokens=2000, count_tokens=words)
    assert [t.turn_index for t in window.verbatim] == [2]  # exchanges are never split
    assert [t.turn_index for t in window.to_summarize] == [0, 1]


def test_working_memory_always_keeps_the_newest_turn() -> None:
    turns = _turns(["short", "reply", "x " * 5000])
    window = select_working_memory(turns, max_turns=10, max_tokens=2000, count_tokens=words)
    assert [t.turn_index for t in window.verbatim] == [2]


def test_working_memory_limits_come_from_config(store: MemoryStore) -> None:
    cfg = load_config().working_memory
    for i in range(24):  # 12 exchanges
        store.append_turn("c1", "u_anna", "user" if i % 2 == 0 else "assistant", f"turn {i}")
    window = select_working_memory(
        store.turns("c1"), cfg.max_turns, cfg.max_tokens, count_tokens=words
    )
    assert cfg.max_turns == 10
    assert len(window.verbatim) == 2 * cfg.max_turns
    assert len(window.to_summarize) == 4
