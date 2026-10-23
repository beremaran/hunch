"""Snapshot and rollback of the adaptive layer (Phase 7, nightly steps 1 and 8).

The snapshot is a full SQLite backup taken before the night's work. A rollback restores every
table from it except the append-only logs (invariant 1: the raw episodes, the admin archive and
the other trigger-guarded logs never lose a row, and the outreach log stays what was sent). The
sqlite-vec index is restored through its virtual table; its shadow tables follow on their own.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from hunch.observability.turn_log import _is_within
from hunch.values.core import DEFAULT_CORE_DIR

# Logs that keep every row through a rollback; the night's own entries stay as a record.
KEEP = frozenset({
    "episodes", "admin_archive", "memory_access", "memory_affect_log", "memory_trace_log",
    "mood_log", "outreach_log",
})  # fmt: skip
VECTOR_TABLES = ("memory_vec",)
# Kept logs that point at memories: a memory formed during the night that a log already refers to
# stays as a tombstone (forgotten = 1, no cues, no vector), invisible like an admin forget.
_MEMORY_REFS = ("memory_access", "memory_affect_log", "memory_trace_log")


@dataclass(frozen=True, slots=True)
class Snapshot:
    path: Path
    taken_at: float


class SnapshotError(ValueError):
    pass


def outside_core(directory: Path) -> Path:
    """The nightly job writes only outside core/ (invariant 3)."""
    if _is_within(directory.resolve(), DEFAULT_CORE_DIR):
        raise SnapshotError(f"{directory} must be outside the core values dir")
    return directory


def take_snapshot(db: sqlite3.Connection, directory: Path, now: float) -> Snapshot:
    outside_core(directory).mkdir(parents=True, exist_ok=True)
    path = directory / f"hunch-{datetime.fromtimestamp(now):%Y%m%d-%H%M%S}.db"
    target = sqlite3.connect(path)
    try:
        db.backup(target)
    finally:
        target.close()
    return Snapshot(path, now)


def restored_tables(db: sqlite3.Connection) -> list[str]:
    """The tables a rollback rewrites, in name order."""
    names = [n for (n,) in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")]
    shadow = tuple(f"{v}_" for v in VECTOR_TABLES)
    return sorted(
        n for n in names
        if n not in KEEP and not n.startswith("sqlite_") and not n.startswith(shadow)
    )  # fmt: skip


def rollback(db: sqlite3.Connection, snapshot: Snapshot) -> list[str]:
    """Restores the adaptive layer from `snapshot`; returns the tables it rewrote."""
    tables = restored_tables(db)
    db.execute("ATTACH DATABASE ? AS snap", (str(snapshot.path),))
    try:
        in_snap = {n for (n,) in db.execute("SELECT name FROM snap.sqlite_master")}
        referenced = " UNION ".join(f"SELECT memory_id FROM main.{t}" for t in _MEMORY_REFS)
        orphans = db.execute(
            "SELECT * FROM main.memories WHERE id NOT IN (SELECT id FROM snap.memories)"
            f" AND id IN ({referenced})"
        ).fetchall()
        with db:
            db.execute("PRAGMA defer_foreign_keys = ON")
            for t in tables:
                db.execute(f'DELETE FROM main."{t}"')
                if t not in in_snap:
                    continue  # created after the snapshot: emptied
                if t in VECTOR_TABLES:
                    db.execute(f'INSERT INTO main."{t}" (rowid, embedding)'
                               f' SELECT rowid, embedding FROM snap."{t}"')  # fmt: skip
                    continue
                cols = [c for _, c, *_ in db.execute(f'PRAGMA main.table_info("{t}")')]
                names = ", ".join(f'"{c}"' for c in cols)
                db.execute(f'INSERT INTO main."{t}" ({names}) SELECT {names} FROM snap."{t}"')
            if orphans:
                cols = [c for _, c, *_ in db.execute('PRAGMA main.table_info("memories")')]
                gone = cols.index("forgotten")
                marks = ", ".join("?" * len(cols))
                db.executemany(
                    f"INSERT INTO main.memories VALUES ({marks})",
                    [(*row[:gone], 1, *row[gone + 1 :]) for row in orphans],
                )
    finally:
        db.execute("DETACH DATABASE snap")
    return tables
