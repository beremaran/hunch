"""SQLite + sqlite-vec store for raw turns (episodes) and memories.

- episodes: append-only raw log. UPDATE and DELETE are blocked by triggers inside the database,
  so not even a buggy code path can rewrite history (invariant 1).
- memories: dual-coded memories; every row has owner_user and privacy (invariant 8).
- memory_cues: cue bonds, used for the fan effect (how many memories share a cue).
- memory_access: append-only log of recall times, for base-level activation.
- memory_affect_log: append-only history of a memory's affect: the encoded value first, then every
  reconsolidation drift. The raw episode never changes; only the "memory of it" does.
- memory_vec: sqlite-vec index over memory embeddings.
- hunches (Phase 4): every Hunch with its sealed source refs; only the reflection code reads the
  sources, and nothing from this table reaches a prompt except through a realisation.
- beliefs (Phase 4): explicit beliefs from justified hunch sources (confidence + evidence ids).
- memory_trace_log (Phase 4): append-only history of a lower trace weakened by reflection.
- Phase 5 (forgetting): memory_derivations links realisation memories to the memory a hunch
  reflection revealed; episode_marks hides raw turns from AI views without touching them
  ("closed" by a user forget: shown as a placeholder; "forgotten" by the admin: left out);
  admin_archive keeps, append-only, everything an admin forget removed from AI-visible stores.
  A forgotten memory stays as a tombstone row (forgotten = 1, empty summary, no cues, no vector)
  because the append-only access/affect/trace logs reference it; every read here skips it.
- memory_repeats (Phase 7): memories that say exactly what an older one of the same user says;
  the nightly job fades them and strengthens the older one (repeated experience consolidates).
  memory_labels (Phase 7): filler or meaningful, set once per memory by the nightly job.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import sqlite_vec

from hunch.memory.schema import Episode, Memory, Role
from hunch.reflection.records import Belief, Hunch, SourceRef

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

CREATE TABLE IF NOT EXISTS hunches (
    id TEXT PRIMARY KEY,
    owner_user TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    turn_id TEXT NOT NULL,
    episode_ref TEXT NOT NULL REFERENCES episodes(id),
    message_cues TEXT NOT NULL,
    created_at REAL NOT NULL,
    valence REAL NOT NULL,
    intensity REAL NOT NULL,
    sources TEXT NOT NULL,
    revealed_level INTEGER NOT NULL DEFAULT 0 CHECK (revealed_level BETWEEN 0 AND 3),
    verdict TEXT CHECK (verdict IN ('justified', 'unjustified'))
);
CREATE TABLE IF NOT EXISTS beliefs (
    id TEXT PRIMARY KEY,
    owner_user TEXT NOT NULL,
    text TEXT NOT NULL,
    confidence REAL NOT NULL,
    evidence TEXT NOT NULL,
    hunch_id TEXT NOT NULL REFERENCES hunches(id),
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_trace_log (
    memory_id TEXT NOT NULL REFERENCES memories(id),
    t REAL NOT NULL,
    salience REAL NOT NULL,
    arousal REAL NOT NULL,
    reason TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS memory_trace_log_no_update BEFORE UPDATE ON memory_trace_log
BEGIN SELECT RAISE(ABORT, 'memory_trace_log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS memory_trace_log_no_delete BEFORE DELETE ON memory_trace_log
BEGIN SELECT RAISE(ABORT, 'memory_trace_log is append-only'); END;

CREATE TABLE IF NOT EXISTS memory_derivations (
    derived_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('realisation')),
    source_id TEXT NOT NULL,
    hunch_id TEXT,
    PRIMARY KEY (derived_id, source_id)
);
CREATE INDEX IF NOT EXISTS memory_derivations_by_source ON memory_derivations(source_id);
CREATE TABLE IF NOT EXISTS memory_repeats (
    repeat_id TEXT PRIMARY KEY,
    survivor_id TEXT NOT NULL,
    merged_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS memory_labels (
    memory_id TEXT PRIMARY KEY,
    label TEXT NOT NULL CHECK (label IN ('filler', 'meaningful')),
    labelled_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS episode_marks (
    episode_id TEXT PRIMARY KEY REFERENCES episodes(id),
    mark TEXT NOT NULL CHECK (mark IN ('closed', 'forgotten')),
    memory_id TEXT,
    t REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS admin_archive (
    t REAL NOT NULL,
    kind TEXT NOT NULL,
    item_id TEXT NOT NULL,
    owner_user TEXT NOT NULL,
    reason TEXT NOT NULL,
    record TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS admin_archive_no_update BEFORE UPDATE ON admin_archive
BEGIN SELECT RAISE(ABORT, 'admin_archive is append-only'); END;
CREATE TRIGGER IF NOT EXISTS admin_archive_no_delete BEFORE DELETE ON admin_archive
BEGIN SELECT RAISE(ABORT, 'admin_archive is append-only'); END;
"""
# Columns added after Phase 2: (table, column, declaration). Older databases are migrated on open.
_MIGRATIONS = (
    ("memories", "kind",
     "TEXT NOT NULL DEFAULT 'episode' CHECK (kind IN ('episode', 'realisation'))"),
    ("memories", "category", "TEXT"),
    ("memories", "forgotten", "INTEGER NOT NULL DEFAULT 0"),
    ("beliefs", "suppressed", "INTEGER NOT NULL DEFAULT 0"),
)  # fmt: skip
# What the AI sees of a turn closed by a user "forget" (Berk, Phase 5); the raw turn is unchanged.
CLOSED_TURN = {
    "user": "(something they asked you to close; you agreed not to bring it up)",
    "assistant": "(your reply about that closed topic)",
}
_MEMORY_COLUMNS = (
    "id, owner_user, privacy, episode_ref, summary, valence, arousal, salience, created_at,"
    " suppressed, kind, category"
)
_LIVE = "forgotten = 0"  # tombstones of admin-forgotten memories are never read


class StoreError(RuntimeError):
    pass


def _is_within(path: Path, parent: Path) -> bool:
    path, parent = Path(os.path.normcase(path)), Path(os.path.normcase(parent))
    return path == parent or parent in path.parents


@dataclass(frozen=True, slots=True)
class WorkingMemoryWindow:
    verbatim: tuple[Episode, ...]  # newest turns that fit both limits, oldest first
    to_summarize: tuple[Episode, ...]  # older turns, to be folded into the session summary


def group_exchanges(turns: Sequence[Episode]) -> list[list[Episode]]:
    """One exchange (= one working-memory turn, Berk) is a user message plus Hunch's replies to
    it. Assistant messages before the first user message (a proactive opener) form their own."""
    exchanges: list[list[Episode]] = []
    for turn in turns:
        if turn.role == "user" or not exchanges:
            exchanges.append([turn])
        else:
            exchanges[-1].append(turn)
    return exchanges


def select_working_memory(
    turns: Sequence[Episode],
    max_turns: int,
    max_tokens: int,
    count_tokens: Callable[[str], int],
) -> WorkingMemoryWindow:
    """Keep the newest exchanges verbatim within max_turns exchanges and max_tokens; the rest get
    summarized. Exchanges are never split. The newest exchange is always kept, even if it alone
    exceeds max_tokens.
    """
    kept: list[list[Episode]] = []
    used = 0
    for exchange in reversed(group_exchanges(turns)):
        cost = sum(count_tokens(t.text) for t in exchange)
        if kept and (len(kept) >= max_turns or used + cost > max_tokens):
            break
        kept.append(exchange)
        used += cost
    verbatim = [t for exchange in reversed(kept) for t in exchange]
    older = turns[: len(turns) - len(verbatim)]
    return WorkingMemoryWindow(verbatim=tuple(verbatim), to_summarize=tuple(older))


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
        # The bot calls the store from worker threads; HunchChannel locks every call.
        self.db = sqlite3.connect(target, check_same_thread=False)
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.enable_load_extension(True)
        sqlite_vec.load(self.db)
        self.db.enable_load_extension(False)
        self.db.executescript(_SCHEMA)
        for table, column, decl in _MIGRATIONS:
            columns = {row[1] for row in self.db.execute(f"PRAGMA table_info({table})")}
            if column not in columns:
                self.db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
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
        """Turns of one conversation as the AI may see them, oldest first; with limit, only the
        newest `limit`. A turn closed by a user "forget" shows as a placeholder; one forgotten
        by the admin is left out (Phase 5). The raw turns never change (raw_turns)."""
        sql = (
            "SELECT e.*, m.mark FROM episodes e LEFT JOIN episode_marks m ON m.episode_id = e.id"
            " WHERE e.conversation_id = ? AND COALESCE(m.mark, '') != 'forgotten'"
            " ORDER BY e.turn_index DESC"
        )
        params: tuple = (conversation_id,)
        if limit is not None:
            sql += " LIMIT ?"
            params += (limit,)
        out = []
        for *row, mark in reversed(self.db.execute(sql, params).fetchall()):
            ep = Episode(*row)
            out.append(replace(ep, text=CLOSED_TURN[ep.role]) if mark == "closed" else ep)
        return out

    def user_messages(self, user: str, since: float) -> list[tuple[float, str]]:
        """(time, text) of what `user` wrote since `since`, across conversations, oldest first,
        hidden like `turns` (Phase 7: the nightly job learns active hours and reactions)."""
        rows = self.db.execute(
            "SELECT e.created_at, e.text, m.mark FROM episodes e"
            " LEFT JOIN episode_marks m ON m.episode_id = e.id"
            " WHERE e.owner_user = ? AND e.role = 'user' AND e.created_at >= ?"
            " AND COALESCE(m.mark, '') != 'forgotten' ORDER BY e.created_at",
            (user, since),
        ).fetchall()
        return [(at, CLOSED_TURN["user"] if mark == "closed" else text) for at, text, mark in rows]

    def raw_turns(self, conversation_id: str) -> list[Episode]:
        """Every raw turn of a conversation, unchanged (admin)."""
        rows = self.db.execute(
            "SELECT * FROM episodes WHERE conversation_id = ? ORDER BY turn_index",
            (conversation_id,),
        ).fetchall()
        return [Episode(*row) for row in rows]

    def mark_episodes(
        self, episode_ids: Iterable[str], mark: str, memory_id: str | None, at: float
    ) -> None:
        """Hide raw turns from AI views ("closed" or "forgotten"); "forgotten" wins."""
        with self.db:
            for eid in episode_ids:
                self.db.execute(
                    "INSERT INTO episode_marks VALUES (?, ?, ?, ?) ON CONFLICT(episode_id) DO"
                    " UPDATE SET mark = excluded.mark, t = excluded.t"
                    " WHERE excluded.mark = 'forgotten'",
                    (eid, mark, memory_id, at),
                )

    def reply_episodes(self, episode_id: str) -> list[str]:
        """The assistant turns that answered a user turn (up to the next user turn)."""
        ep = self.episode(episode_id)
        rows = self.db.execute(
            "SELECT id, role FROM episodes WHERE conversation_id = ? AND turn_index > ?"
            " ORDER BY turn_index",
            (ep.conversation_id, ep.turn_index),
        ).fetchall()
        out = []
        for eid, role in rows:
            if role == "user":
                break
            out.append(eid)
        return out

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
                f"INSERT INTO memories ({_MEMORY_COLUMNS})"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (memory.id, memory.owner_user, memory.privacy, memory.episode_ref, memory.summary,
                 memory.affect[0], memory.affect[1], memory.salience, memory.created_at,
                 int(memory.suppressed), memory.kind, memory.category),
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
            f"SELECT {_MEMORY_COLUMNS} FROM memories WHERE id = ? AND {_LIVE}", (memory_id,)
        ).fetchone()
        if row is None:
            raise KeyError(memory_id)
        return self._to_memory(row)

    def live(self, memory_id: str) -> Memory | None:
        """The memory, or None if it does not exist or was forgotten by the admin."""
        try:
            return self.memory(memory_id)
        except KeyError:
            return None

    def memories(self, owner_user: str | None = None) -> list[Memory]:
        sql = f"SELECT {_MEMORY_COLUMNS} FROM memories WHERE {_LIVE}"
        rows = (
            self.db.execute(sql + " AND owner_user = ? ORDER BY rowid", (owner_user,))
            if owner_user is not None
            else self.db.execute(sql + " ORDER BY rowid")
        ).fetchall()
        return [self._to_memory(r) for r in rows]

    def _to_memory(self, row: tuple) -> Memory:
        (mid, owner, privacy, ep, summary, valence, arousal, salience, created, suppressed, kind,
         category) = row  # fmt: skip
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
            access_times=times, suppressed=bool(suppressed), kind=kind, category=category,
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

    def set_salience(self, memory_id: str, salience: float, reason: str, at: float) -> None:
        """Nightly fading and strengthening (Phase 7); logged like a weakened trace."""
        m = self.memory(memory_id)
        with self.db:
            self.db.execute("UPDATE memories SET salience = ? WHERE id = ?", (salience, memory_id))
            self.db.execute(
                "INSERT INTO memory_trace_log VALUES (?, ?, ?, ?, ?)",
                (memory_id, at, salience, m.affect[1], reason),
            )

    def mark_repeat(self, repeat_id: str, survivor_id: str, at: float) -> None:
        """`repeat_id` says the same as `survivor_id` (Phase 7, nightly step 6)."""
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO memory_repeats VALUES (?, ?, ?)",
                            (repeat_id, survivor_id, at))  # fmt: skip

    def repeat_ids(self) -> set[str]:
        return {r for (r,) in self.db.execute("SELECT repeat_id FROM memory_repeats")}

    def label_memory(self, memory_id: str, label: str, at: float) -> None:
        """Filler or meaningful, decided once by the nightly job (Phase 7, step 6b)."""
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO memory_labels VALUES (?, ?, ?)",
                            (memory_id, label, at))  # fmt: skip

    def labelled_ids(self) -> set[str]:
        return {m for (m,) in self.db.execute("SELECT memory_id FROM memory_labels")}

    def said_before(self, memory: Memory) -> str | None:
        """What Hunch said right before the turn a memory came from, as the AI may see it."""
        ep = self.episode(memory.episode_ref)
        earlier = [t for t in self.turns(ep.conversation_id) if t.turn_index < ep.turn_index]
        return earlier[-1].text if earlier and earlier[-1].role == "assistant" else None

    def weaken_trace(self, memory_id: str, factor: float, reason: str, at: float) -> Memory:
        """Multiply a lower trace's salience and arousal by `factor` (an unjustified hunch
        source, Phase 4). Both logs are append-only; the raw episode never changes."""
        m = self.memory(memory_id)
        salience = m.salience * factor
        valence, arousal = m.affect[0], m.affect[1] * factor
        with self.db:
            self.db.execute(
                "UPDATE memories SET salience = ?, arousal = ? WHERE id = ?",
                (salience, arousal, memory_id),
            )
            self.db.execute(
                "INSERT INTO memory_trace_log VALUES (?, ?, ?, ?, ?)",
                (memory_id, at, salience, arousal, reason),
            )
            self.db.execute(
                "INSERT INTO memory_affect_log VALUES (?, ?, ?, ?, ?)",
                (memory_id, at, valence, arousal, reason),
            )
        return self.memory(memory_id)

    def trace_history(self, memory_id: str) -> list[tuple[float, float, float, str]]:
        """(t, salience, arousal, reason) for every weakening, oldest first."""
        return list(
            self.db.execute(
                "SELECT t, salience, arousal, reason FROM memory_trace_log WHERE memory_id = ?"
                " ORDER BY rowid",
                (memory_id,),
            )
        )

    # --- hunches and beliefs (Phase 4) ---------------------------------------------------------

    def add_hunch(self, hunch: Hunch) -> None:
        sources = [[s.memory_id, s.strength, s.relevant] for s in hunch._source_refs]
        with self.db:
            self.db.execute(
                "INSERT INTO hunches VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (hunch.id, hunch.owner_user, hunch.conversation_id, hunch.turn_id,
                 hunch.episode_ref, json.dumps(hunch.message_cues), hunch.created_at,
                 hunch.valence, hunch.intensity, json.dumps(sources), hunch.revealed_level,
                 hunch.verdict),
            )  # fmt: skip

    def hunch(self, hunch_id: str) -> Hunch:
        row = self.db.execute("SELECT * FROM hunches WHERE id = ?", (hunch_id,)).fetchone()
        if row is None:
            raise KeyError(hunch_id)
        return _to_hunch(row)

    def hunches_since(self, t: float) -> list[Hunch]:
        rows = self.db.execute(
            "SELECT * FROM hunches WHERE created_at >= ? ORDER BY created_at, id", (t,)
        ).fetchall()
        return [_to_hunch(r) for r in rows]

    def update_hunch(self, hunch_id: str, revealed_level: int, verdict: str | None) -> None:
        with self.db:
            cur = self.db.execute(
                "UPDATE hunches SET revealed_level = ?, verdict = ? WHERE id = ?",
                (revealed_level, verdict, hunch_id),
            )
            if cur.rowcount != 1:
                raise KeyError(hunch_id)

    def add_belief(self, belief: Belief) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO beliefs (id, owner_user, text, confidence, evidence, hunch_id,"
                " created_at, suppressed) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (belief.id, belief.owner_user, belief.text, belief.confidence,
                 json.dumps(list(belief.evidence)), belief.hunch_id, belief.created_at,
                 int(belief.suppressed)),
            )  # fmt: skip

    def beliefs(self, owner_user: str | None = None) -> list[Belief]:
        sql = (
            "SELECT id, owner_user, text, confidence, evidence, hunch_id, created_at, suppressed"
            " FROM beliefs"
        )
        rows = (
            self.db.execute(sql + " WHERE owner_user = ? ORDER BY rowid", (owner_user,))
            if owner_user is not None
            else self.db.execute(sql + " ORDER BY rowid")
        ).fetchall()
        return [
            Belief(bid, owner, text, conf, tuple(json.loads(ev)), hid, t, bool(sup))
            for bid, owner, text, conf, ev, hid, t, sup in rows
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
        self,
        query: np.ndarray,
        k: int,
        owner_user: str | None = None,
        visible_to: str | None = None,
    ) -> list[tuple[Memory, float]]:
        """Nearest memories by cosine distance (candidate generation, not activation).

        owner_user: only that user's memories. visible_to: that user's memories plus other
        users' general ones (never another user's private memory, invariant 6).
        """
        if owner_user is not None and visible_to is not None:
            raise ValueError("pass owner_user or visible_to, not both")
        vec = sqlite_vec.serialize_float32(np.asarray(query, dtype=np.float32).tolist())
        # Over-fetch when filtering, since vec0 applies k before the join.
        fetch = k if owner_user is None and visible_to is None else k * 4
        rows = self.db.execute(
            "SELECT m.id, v.distance FROM memory_vec v JOIN memories m ON m.rowid = v.rowid"
            " WHERE v.embedding MATCH ? AND k = ? ORDER BY v.distance",
            (vec, fetch),
        ).fetchall()
        out = [(m, float(dist)) for mid, dist in rows if (m := self.live(mid)) is not None]
        if owner_user is not None:
            out = [(m, d) for m, d in out if m.owner_user == owner_user]
        if visible_to is not None:
            out = [(m, d) for m, d in out if _visible(m, visible_to)]
        return out[:k]

    def with_cues(self, cues: Iterable[str], visible_to: str) -> list[Memory]:
        """Memories visible to the user that share at least one of the cues."""
        cues = sorted(set(cues))
        if not cues:
            return []
        marks = ",".join("?" * len(cues))
        ids = [
            mid
            for (mid,) in self.db.execute(
                "SELECT DISTINCT c.memory_id FROM memory_cues c JOIN memories m"
                f" ON m.id = c.memory_id WHERE c.cue IN ({marks}) AND m.forgotten = 0"
                " AND (m.owner_user = ? OR m.privacy = 'general') ORDER BY m.rowid",
                (*cues, visible_to),
            )
        ]
        return [self.memory(mid) for mid in ids]

    def memory_ids_from_conversation(self, conversation_id: str) -> set[str]:
        """Memories encoded from this conversation's own turns."""
        return {
            mid
            for (mid,) in self.db.execute(
                "SELECT m.id FROM memories m JOIN episodes e ON e.id = m.episode_ref"
                " WHERE e.conversation_id = ? AND m.forgotten = 0",
                (conversation_id,),
            )
        }

    def private_memories_of_others(self, user: str) -> list[Memory]:
        """Other users' private memories (for the disclosure check, never for a prompt)."""
        rows = self.db.execute(
            "SELECT id FROM memories WHERE owner_user != ? AND privacy = 'private'"
            f" AND {_LIVE} ORDER BY rowid",
            (user,),
        ).fetchall()
        return [self.memory(mid) for (mid,) in rows]

    def other_users_private(
        self, user: str, cues: Iterable[str], query: np.ndarray | None, k: int
    ) -> list[tuple[Memory, float | None]]:
        """Other users' private memories that share a cue with the message or are among the k
        nearest by embedding, with their similarity (None if found by cue only). Mediation
        (Berk, Phase 5): they may only act from below. Never for a reply prompt."""
        found: dict[str, tuple[Memory, float | None]] = {}
        if query is not None and k > 0:
            vec = sqlite_vec.serialize_float32(np.asarray(query, dtype=np.float32).tolist())
            rows = self.db.execute(
                "SELECT m.id, v.distance FROM memory_vec v JOIN memories m ON m.rowid = v.rowid"
                " WHERE v.embedding MATCH ? AND k = ? ORDER BY v.distance",
                (vec, k * 8),
            ).fetchall()
            for mid, dist in rows:
                m = self.live(mid)
                if m and m.owner_user != user and m.privacy == "private" and len(found) < k:
                    found[mid] = (m, 1.0 - float(dist))
        cues = sorted(set(cues))
        if cues:
            marks = ",".join("?" * len(cues))
            for (mid,) in self.db.execute(
                "SELECT DISTINCT c.memory_id FROM memory_cues c JOIN memories m"
                f" ON m.id = c.memory_id WHERE c.cue IN ({marks}) AND m.forgotten = 0"
                " AND m.owner_user != ? AND m.privacy = 'private' ORDER BY m.rowid",
                (*cues, user),
            ):
                found.setdefault(mid, (self.memory(mid), None))
        return list(found.values())

    # --- privacy and forgetting (Phase 5) --------------------------------------------------------

    def set_privacy(self, memory_ids: Iterable[str], privacy: str) -> None:
        if privacy not in ("private", "general"):
            raise StoreError(f"privacy must be private or general, got {privacy!r}")
        with self.db:
            for mid in memory_ids:
                self.db.execute("UPDATE memories SET privacy = ? WHERE id = ?", (privacy, mid))

    def memories_of_episode(self, episode_id: str) -> list[Memory]:
        rows = self.db.execute(
            f"SELECT id FROM memories WHERE episode_ref = ? AND {_LIVE} ORDER BY rowid",
            (episode_id,),
        ).fetchall()
        return [self.memory(mid) for (mid,) in rows]

    def suppress(self, memory_ids: Iterable[str]) -> None:
        """A user "forget": the memories never reach reasoning again; their lower traces act on."""
        with self.db:
            for mid in memory_ids:
                self.db.execute("UPDATE memories SET suppressed = 1 WHERE id = ?", (mid,))

    def add_derivation(self, derived_id: str, kind: str, source_id: str, hunch_id: str) -> None:
        with self.db:
            self.db.execute(
                "INSERT OR IGNORE INTO memory_derivations VALUES (?, ?, ?, ?)",
                (derived_id, kind, source_id, hunch_id),
            )

    def derived_from(self, source_id: str) -> list[str]:
        """Realisation memories a hunch reflection made from this memory."""
        return [
            d
            for (d,) in self.db.execute(
                "SELECT derived_id FROM memory_derivations WHERE source_id = ? ORDER BY rowid",
                (source_id,),
            )
        ]

    def beliefs_with_evidence(self, memory_id: str) -> list[str]:
        return [
            b
            for (b,) in self.db.execute(
                "SELECT DISTINCT b.id FROM beliefs b, json_each(b.evidence) e WHERE e.value = ?"
                " ORDER BY b.rowid",
                (memory_id,),
            )
        ]

    def suppress_beliefs(self, belief_ids: Iterable[str]) -> None:
        with self.db:
            for bid in belief_ids:
                self.db.execute("UPDATE beliefs SET suppressed = 1 WHERE id = ?", (bid,))

    def _archive(
        self, kind: str, item_id: str, owner: str, reason: str, record: dict, at: float
    ) -> None:
        self.db.execute(
            "INSERT INTO admin_archive VALUES (?, ?, ?, ?, ?, ?)",
            (at, kind, item_id, owner, reason, json.dumps(record, ensure_ascii=False)),
        )

    def tombstone(self, memory_id: str, reason: str, at: float) -> None:
        """Admin forget: copy the memory to the admin archive and remove it from every AI-visible
        store: cues and vector deleted, summary emptied, row marked forgotten."""
        m = self.memory(memory_id)
        (rowid,) = self.db.execute(
            "SELECT rowid FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        record = {
            "id": m.id, "owner_user": m.owner_user, "privacy": m.privacy,
            "episode_ref": m.episode_ref, "summary": m.summary, "cues": m.cues,
            "affect": list(m.affect), "salience": m.salience, "created_at": m.created_at,
            "suppressed": m.suppressed, "kind": m.kind, "category": m.category,
        }  # fmt: skip
        with self.db:
            self._archive("memory", m.id, m.owner_user, reason, record, at)
            self.db.execute("DELETE FROM memory_cues WHERE memory_id = ?", (memory_id,))
            self.db.execute("DELETE FROM memory_vec WHERE rowid = ?", (rowid,))
            self.db.execute(
                "UPDATE memories SET summary = '', forgotten = 1 WHERE id = ?", (memory_id,)
            )

    def remove_belief(self, belief_id: str, reason: str, at: float) -> None:
        b = next(x for x in self.beliefs() if x.id == belief_id)
        record = {
            "id": b.id, "owner_user": b.owner_user, "text": b.text, "confidence": b.confidence,
            "evidence": list(b.evidence), "hunch_id": b.hunch_id, "created_at": b.created_at,
        }  # fmt: skip
        with self.db:
            self._archive("belief", b.id, b.owner_user, reason, record, at)
            self.db.execute("DELETE FROM beliefs WHERE id = ?", (belief_id,))

    def drop_hunch_source(self, memory_id: str) -> list[str]:
        """Remove a memory from every hunch's sealed source refs; returns the hunch ids."""
        changed = []
        rows = self.db.execute("SELECT id, sources FROM hunches").fetchall()
        with self.db:
            for hid, raw in rows:
                sources = json.loads(raw)
                kept = [s for s in sources if s[0] != memory_id]
                if len(kept) != len(sources):
                    self.db.execute(
                        "UPDATE hunches SET sources = ? WHERE id = ?", (json.dumps(kept), hid)
                    )
                    changed.append(hid)
        return changed

    def archive(self) -> list[dict]:
        """The admin archive, oldest first (admin only, never for a prompt)."""
        return [
            {"t": t, "kind": k, "id": i, "owner_user": o, "reason": r, "record": json.loads(rec)}
            for t, k, i, o, r, rec in self.db.execute("SELECT * FROM admin_archive ORDER BY rowid")
        ]


def _to_hunch(row: tuple) -> Hunch:
    hid, owner, conv, turn_id, ep, cues, created, valence, intensity, sources, level, verdict = row
    refs = tuple(SourceRef(mid, float(s), bool(rel)) for mid, s, rel in json.loads(sources))
    return Hunch(
        hid, owner, conv, turn_id, ep, json.loads(cues), created, valence, intensity, refs,
        level, verdict,
    )  # fmt: skip


def _visible(memory: Memory, user: str) -> bool:
    return memory.owner_user == user or memory.privacy == "general"
