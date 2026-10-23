"""Snapshot and rollback of the adaptive layer (Phase 7, nightly steps 1 and 8)."""

from __future__ import annotations

from pathlib import Path

from hunch.channels.store import ChannelStore
from hunch.consolidation.snapshot import KEEP, restored_tables, rollback, take_snapshot
from hunch.loops.learning import LearnedInitiative
from hunch.memory.store import MemoryStore
from tests.fakes import HashEmbedder
from tests.pipeline_support import DIM, NOW, seed_memory


def test_rollback_restores_memories_and_profiles_but_keeps_the_logs(
    pipe_store: MemoryStore, tmp_path: Path
) -> None:
    channels = ChannelStore(pipe_store.db)
    seed_memory(pipe_store, "old", 'They said: "my sister moved to Lyon"', {}, 2, privacy="general")
    channels.save_initiative(LearnedInitiative("u_berk", 9, 22, 2, None, NOW))
    snap = take_snapshot(pipe_store.db, tmp_path / "snapshots", NOW)

    # The night's work, then a failed golden test: all of it must go back.
    seed_memory(pipe_store, "new", 'They said: "the sister fact, rewritten"', {}, 0)
    pipe_store.db.execute("UPDATE memories SET salience = 0.01 WHERE id = 'old'")
    pipe_store.db.commit()
    channels.save_initiative(LearnedInitiative("u_berk", 12, 18, 3, None, NOW + 60))
    # A message that arrived during the night stays (raw log, append-only).
    ep = pipe_store.append_turn("c-night", "u_berk", "user", "still up?", at=NOW + 30)
    channels.log_outreach("u_berk", "memory", NOW + 40)

    rewritten = rollback(pipe_store.db, snap)

    assert {m.id for m in pipe_store.memories("u_berk")} == {"old"}
    assert pipe_store.memory("old").salience == 0.2
    assert channels.initiative("u_berk") == LearnedInitiative("u_berk", 9, 22, 2, None, NOW)
    assert [e.id for e in pipe_store.turns("c-night")] == [ep.id]
    assert channels.outreach_times("u_berk", 0.0) == [NOW + 40]
    assert not KEEP & set(rewritten)
    # The night's memory has an access log row, so it stays as an invisible tombstone.
    row = pipe_store.db.execute("SELECT forgotten FROM memories WHERE id = 'new'").fetchone()
    assert row == (1,)
    cues = pipe_store.db.execute("SELECT COUNT(*) FROM memory_cues WHERE memory_id = 'new'")
    assert cues.fetchone() == (0,)
    query = HashEmbedder(DIM).embed_queries(['They said: "the sister fact, rewritten"'])[0]
    assert {m.id for m, _ in pipe_store.similar(query, k=5)} == {"old"}


def test_append_only_logs_and_vector_shadow_tables_are_never_rewritten(pipe_store) -> None:
    tables = restored_tables(pipe_store.db)
    assert "memories" in tables and "memory_vec" in tables
    assert not [t for t in tables if t.startswith("memory_vec_") or t.startswith("sqlite_")]
    assert not KEEP & set(tables)


def test_snapshots_are_never_written_inside_core(pipe_store: MemoryStore) -> None:
    import pytest

    from hunch.consolidation.snapshot import SnapshotError
    from hunch.values.core import DEFAULT_CORE_DIR

    with pytest.raises(SnapshotError):
        take_snapshot(pipe_store.db, DEFAULT_CORE_DIR / "snapshots", NOW)
    assert not (DEFAULT_CORE_DIR / "snapshots").exists()
