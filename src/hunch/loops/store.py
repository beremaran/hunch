"""Open loops in SQLite: what the user said they would do, and when to follow up (Phase 6)."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Literal

Status = Literal["open", "sent", "closed"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS open_loops (
    id TEXT PRIMARY KEY,
    user TEXT NOT NULL,
    topic TEXT NOT NULL,
    user_said TEXT NOT NULL,
    question TEXT NOT NULL,
    privacy TEXT NOT NULL CHECK (privacy IN ('private', 'general')),
    follow_up_at REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'sent', 'closed')),
    created_at REAL NOT NULL,
    sent_at REAL
);
CREATE INDEX IF NOT EXISTS open_loops_due ON open_loops (status, follow_up_at);
"""


@dataclass(frozen=True, slots=True)
class OpenLoop:
    id: str
    user: str
    topic: str
    user_said: str
    question: str  # the follow-up question the model is asked to phrase
    privacy: Literal["private", "general"]
    follow_up_at: float  # unix seconds
    created_at: float
    status: Status = "open"
    sent_at: float | None = None


class LoopStore:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db
        self.db.executescript(_SCHEMA)
        self.db.commit()

    def add(self, loop: OpenLoop) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO open_loops (id, user, topic, user_said, question, privacy,"
                " follow_up_at, status, created_at, sent_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (loop.id, loop.user, loop.topic, loop.user_said, loop.question, loop.privacy,
                 loop.follow_up_at, loop.status, loop.created_at, loop.sent_at),
            )  # fmt: skip

    def get(self, loop_id: str) -> OpenLoop | None:
        row = self.db.execute(_SELECT + " WHERE id = ?", (loop_id,)).fetchone()
        return None if row is None else _loop(row)

    def due(self, now: float) -> list[OpenLoop]:
        """Open loops whose follow-up time has come, earliest first."""
        rows = self.db.execute(
            _SELECT + " WHERE status = 'open' AND follow_up_at <= ? ORDER BY follow_up_at",
            (now,),
        )
        return [_loop(r) for r in rows]

    def sent_since(self, user: str, since: float) -> int:
        """Follow-ups already sent to this user since `since` (unix seconds): the budget's count."""
        row = self.db.execute(
            "SELECT COUNT(*) FROM open_loops WHERE user = ? AND status = 'sent' AND sent_at >= ?",
            (user, since),
        ).fetchone()
        return int(row[0])

    def mark_sent(self, loop_id: str, at: float) -> None:
        with self.db:
            self.db.execute(
                "UPDATE open_loops SET status = 'sent', sent_at = ?"
                " WHERE id = ? AND status = 'open'",
                (at, loop_id),
            )

    def close(self, loop_id: str) -> None:
        """The user answered, forgot the topic, or the loop no longer applies."""
        with self.db:
            self.db.execute(
                "UPDATE open_loops SET status = 'closed' WHERE id = ? AND status = 'open'",
                (loop_id,),
            )


_SELECT = (
    "SELECT id, user, topic, user_said, question, privacy, follow_up_at, created_at, status,"
    " sent_at FROM open_loops"
)


def _loop(row: tuple) -> OpenLoop:
    loop_id, user, topic, said, question, privacy, follow_up_at, created_at, status, sent_at = row
    return OpenLoop(loop_id, user, topic, said, question, privacy, follow_up_at, created_at,
                    status, sent_at)  # fmt: skip
