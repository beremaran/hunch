"""SQLite + sqlite-vec store for raw turns (episodes) and memories.

- episodes: append-only raw log. UPDATE and DELETE are blocked by triggers inside the database,
  so not even a buggy code path can rewrite history (invariant 1).
- memories: dual-coded memories; every row has owner_user and privacy (invariant 8).
- memory_cues: cue bonds, used for the fan effect (how many memories share a cue).
- memory_access: append-only log of recall times, for base-level activation.
- memory_affect_log: append-only history of a memory's affect: the encoded value first, then every
  reconsolidation drift. The raw episode never changes; only the "memory of it" does.
- memory_vec: sqlite-vec index over memory embeddings.
"""

from __future__ import annotations

import os
import sqlite3
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import sqlite_vec

from hunch.memory.schema import Episode, Memory, Role

_DB_SUFFIXES = (".db", ".sqlite", ".sqlite3")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    owner_user TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    text TEXT NOT NULL,
    created_at REAL NOT NULL,
    UNIQUE (conversation_id, turn_index)
);
CREATE TRIGGER IF NOT EXISTS episodes_no_update BEFORE UPDATE ON episodes
BEGIN SELECT RAISE(ABORT, 'episodes are append-only'); END;
CREATE TRIGGER IF NOT EXISTS episodes_no_delete BEFORE DELETE ON episodes
BEGIN SELECT RAISE(ABORT, 'episodes are append-only'); END;

CREATE TABLE IF NOT EXISTS memories (
    rowid INTEGER PRIMARY KEY,
    id TEXT NOT NULL UNIQUE,
    owner_user TEXT NOT NULL,
    privacy TEXT NOT NULL CHECK (privacy IN ('private', 'general')),
    episode_ref TEXT NOT NULL REFERENCES episodes(id),
    summary TEXT NOT NULL,
    valence REAL NOT NULL,
    arousal REAL NOT NULL,
    salience REAL NOT NULL,
    created_at REAL NOT NULL,
    suppressed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS memory_cues (
    memory_id TEXT NOT NULL REFERENCES memories(id),
    cue TEXT NOT NULL,
    bond REAL NOT NULL,
    PRIMARY KEY (memory_id, cue)
);
CREATE INDEX IF NOT EXISTS memory_cues_by_cue ON memory_cues(cue);
CREATE TABLE IF NOT EXISTS memory_access (
    memory_id TEXT NOT NULL REFERENCES memories(id),
    t REAL NOT NULL
);
CREATE TRIGGER IF NOT EXISTS memory_access_no_update BEFORE UPDATE ON memory_access
BEGIN SELECT RAISE(ABORT, 'memory_access is append-only'); END;
CREATE TRIGGER IF NOT EXISTS memory_access_no_delete BEFORE DELETE ON memory_access
BEGIN SELECT RAISE(ABORT, 'memory_access is append-only'); END;
CREATE TABLE IF NOT EXISTS memory_affect_log (
    memory_id TEXT NOT NULL REFERENCES memories(id),
    t REAL NOT NULL,
    valence REAL NOT NULL,
    arousal REAL NOT NULL,
    reason TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS memory_affect_log_no_update BEFORE UPDATE ON memory_affect_log
BEGIN SELECT RAISE(ABORT, 'memory_affect_log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS memory_affect_log_no_delete BEFORE DELETE ON memory_affect_log
BEGIN SELECT RAISE(ABORT, 'memory_affect_log is append-only'); END;
"""


class StoreError(RuntimeError):
    pass


def _is_within(path: Path, parent: Path) -> bool:
    path, parent = Path(os.path.normcase(path)), Path(os.path.normcase(parent))
    return path == parent or parent in path.parents


@dataclass(frozen=True, slots=True)
class WorkingMemoryWindow:
    verbatim: tuple[Episode, ...]  # newest turns that fit both limits, oldest first
    to_summarize: tuple[Episode, ...]  # older turns, to be folded into the session summary


def select_working_memory(
    turns: Sequence[Episode],
    max_turns: int,
    max_tokens: int,
    count_tokens: Callable[[str], int],
) -> WorkingMemoryWindow:
    """Keep the newest turns verbatim within max_turns and max_tokens; the rest get summarized.

    The newest turn is always kept, even if it alone exceeds max_tokens.
    """
    kept: list[Episode] = []
    used = 0
    for turn in reversed(turns):
        cost = count_tokens(turn.text)
        if kept and (len(kept) >= max_turns or used + cost > max_tokens):
            break
        kept.append(turn)
        used += cost
    kept.reverse()
    older = turns[: len(turns) - len(kept)]
    return WorkingMemoryWindow(verbatim=tuple(kept), to_summarize=tuple(older))


class MemoryStore:
    def __init__(
        self,
        db_path: Path | str,
        core_dir: Path,
        embedding_dim: int,
        clock: Callable[[], float] = time.time,
        new_id: Callable[[], str] = lambda: uuid.uuid4().hex,
    ) -> None:
        self._clock = clock
        self._new_id = new_id
        self.embedding_dim = embedding_dim
        if str(db_path) == ":memory:":
            target = ":memory:"
        else:
            path = Path(db_path).resolve()
            if _is_within(path, core_dir.resolve()):
                raise StoreError(f"database {path} must be outside the core values dir")
            if path.suffix.lower() not in _DB_SUFFIXES:
                raise StoreError(f"database file must end in {_DB_SUFFIXES}, got {path.name}")
            path.parent.mkdir(parents=True, exist_ok=True)
            target = str(path)
        self.db = sqlite3.connect(target)
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.enable_load_extension(True)
        sqlite_vec.load(self.db)
        self.db.enable_load_extension(False)
        self.db.executescript(_SCHEMA)
        self.db.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS memory_vec USING vec0("
            f"embedding float[{int(embedding_dim)}] distance_metric=cosine)"
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    # --- episodes (raw turns) ------------------------------------------------------------------

    def append_turn(
        self,
        conversation_id: str,
        owner_user: str,
        role: Role,
        text: str,
        at: float | None = None,
    ) -> Episode:
        with self.db:
            (last,) = self.db.execute(
                "SELECT COALESCE(MAX(turn_index), -1) FROM episodes WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            ep = Episode(
                id=self._new_id(),
                conversation_id=conversation_id,
                turn_index=last + 1,
                owner_user=owner_user,
                role=role,
                text=text,
                created_at=self._clock() if at is None else at,
            )
            self.db.execute(
                "INSERT INTO episodes VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ep.id, ep.conversation_id, ep.turn_index, ep.owner_user, ep.role, ep.text,
                 ep.created_at),
            )  # fmt: skip
        return ep

    def turns(self, conversation_id: str, limit: int | None = None) -> list[Episode]:
        """Turns of one conversation, oldest first; with limit, only the newest `limit`."""
        sql = "SELECT * FROM episodes WHERE conversation_id = ? ORDER BY turn_index DESC"
        params: tuple = (conversation_id,)
        if limit is not None:
            sql += " LIMIT ?"
            params += (limit,)
        rows = self.db.execute(sql, params).fetchall()
        return [Episode(*row) for row in reversed(rows)]

    def episode(self, episode_id: str) -> Episode:
        row = self.db.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,)).fetchone()
        if row is None:
            raise KeyError(episode_id)
        return Episode(*row)

    # --- memories --------------------------------------------------------------------------------

    def add_memory(self, memory: Memory, embedding: np.ndarray) -> None:
        vec = np.asarray(embedding, dtype=np.float32)
        if vec.shape != (self.embedding_dim,):
            raise StoreError(f"embedding must have shape ({self.embedding_dim},), got {vec.shape}")
        with self.db:
            cur = self.db.execute(
                "INSERT INTO memories (id, owner_user, privacy, episode_ref, summary, valence,"
                " arousal, salience, created_at, suppressed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (memory.id, memory.owner_user, memory.privacy, memory.episode_ref, memory.summary,
                 memory.affect[0], memory.affect[1], memory.salience, memory.created_at,
                 int(memory.suppressed)),
            )  # fmt: skip
            self.db.executemany(
                "INSERT INTO memory_cues VALUES (?, ?, ?)",
                [(memory.id, cue, bond) for cue, bond in memory.cues.items()],
            )
            self.db.executemany(
                "INSERT INTO memory_access VALUES (?, ?)",
                [(memory.id, t) for t in memory.access_times],
            )
            self.db.execute(
                "INSERT INTO memory_affect_log VALUES (?, ?, ?, ?, 'encoded')",
                (memory.id, memory.created_at, memory.affect[0], memory.affect[1]),
            )
            self.db.execute(
                "INSERT INTO memory_vec(rowid, embedding) VALUES (?, ?)",
                (cur.lastrowid, sqlite_vec.serialize_float32(vec.tolist())),
            )

    def memory(self, memory_id: str) -> Memory:
        row = self.db.execute(
            "SELECT id, owner_user, privacy, episode_ref, summary, valence, arousal, salience,"
            " created_at, suppressed FROM memories WHERE id = ?",
            (memory_id,),
        ).fetchone()
        if row is None:
            raise KeyError(memory_id)
        return self._to_memory(row)

    def memories(self, owner_user: str | None = None) -> list[Memory]:
        sql = (
            "SELECT id, owner_user, privacy, episode_ref, summary, valence, arousal, salience,"
            " created_at, suppressed FROM memories"
        )
        rows = (
            self.db.execute(sql + " WHERE owner_user = ? ORDER BY rowid", (owner_user,))
            if owner_user is not None
            else self.db.execute(sql + " ORDER BY rowid")
        ).fetchall()
        return [self._to_memory(r) for r in rows]

    def _to_memory(self, row: tuple) -> Memory:
        mid, owner, privacy, ep, summary, valence, arousal, salience, created, suppressed = row
        cues = dict(
            self.db.execute("SELECT cue, bond FROM memory_cues WHERE memory_id = ?", (mid,))
        )
        times = tuple(
            t
            for (t,) in self.db.execute(
                "SELECT t FROM memory_access WHERE memory_id = ? ORDER BY t", (mid,)
            )
        )
        return Memory(
            id=mid, owner_user=owner, privacy=privacy, episode_ref=ep, summary=summary,
            cues=cues, affect=(valence, arousal), salience=salience, created_at=created,
            access_times=times, suppressed=bool(suppressed),
        )  # fmt: skip

    def record_access(self, memory_id: str, at: float | None = None) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO memory_access VALUES (?, ?)",
                (memory_id, self._clock() if at is None else at),
            )

    def update_affect(
        self, memory_id: str, affect: tuple[float, float], reason: str, at: float | None = None
    ) -> None:
        """Change the current affect and log it (reconsolidation). Episodes never change."""
        valence, arousal = affect
        if not (-1.0 <= valence <= 1.0 and 0.0 <= arousal <= 1.0):
            raise StoreError(f"affect out of range: {affect}")
        t = self._clock() if at is None else at
        with self.db:
            cur = self.db.execute(
                "UPDATE memories SET valence = ?, arousal = ? WHERE id = ?",
                (valence, arousal, memory_id),
            )
            if cur.rowcount != 1:
                raise KeyError(memory_id)
            self.db.execute(
                "INSERT INTO memory_affect_log VALUES (?, ?, ?, ?, ?)",
                (memory_id, t, valence, arousal, reason),
            )

    def affect_history(self, memory_id: str) -> list[tuple[float, float, float, str]]:
        """(t, valence, arousal, reason), oldest first; the first entry is the encoded affect."""
        return [
            (t, v, a, r)
            for t, v, a, r in self.db.execute(
                "SELECT t, valence, arousal, reason FROM memory_affect_log WHERE memory_id = ?"
                " ORDER BY rowid",
                (memory_id,),
            )
        ]

    def cue_fan(self, cue: str, context: frozenset[str] = frozenset()) -> int:
        """How many memories carry this cue; with a context, only those that also carry at least
        one context cue (the fan effect counted in context)."""
        if not context:
            (n,) = self.db.execute(
                "SELECT COUNT(*) FROM memory_cues WHERE cue = ?", (cue,)
            ).fetchone()
            return int(n)
        marks = ",".join("?" * len(context))
        (n,) = self.db.execute(
            "SELECT COUNT(DISTINCT a.memory_id) FROM memory_cues a JOIN memory_cues b"
            f" ON a.memory_id = b.memory_id WHERE a.cue = ? AND b.cue IN ({marks})",
            (cue, *sorted(context)),
        ).fetchone()
        return int(n)

    def similar(
        self, query: np.ndarray, k: int, owner_user: str | None = None
    ) -> list[tuple[Memory, float]]:
        """Nearest memories by cosine distance (candidate generation, not activation)."""
        vec = sqlite_vec.serialize_float32(np.asarray(query, dtype=np.float32).tolist())
        # Over-fetch when filtering by owner, since vec0 applies k before the join.
        fetch = k if owner_user is None else k * 4
        rows = self.db.execute(
            "SELECT m.id, v.distance FROM memory_vec v JOIN memories m ON m.rowid = v.rowid"
            " WHERE v.embedding MATCH ? AND k = ? ORDER BY v.distance",
            (vec, fetch),
        ).fetchall()
        out = [(self.memory(mid), float(dist)) for mid, dist in rows]
        if owner_user is not None:
            out = [(m, d) for m, d in out if m.owner_user == owner_user]
        return out[:k]
