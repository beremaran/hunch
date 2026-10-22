"""Telegram chats and the outreach log (Phase 6). The outreach log counts every message Hunch
writes first, follow-ups and starters alike, against the same daily budget."""

from __future__ import annotations

import sqlite3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS telegram_chats (
    chat_id INTEGER PRIMARY KEY,
    user TEXT NOT NULL UNIQUE,
    last_seen REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS outreach_log (
    user TEXT NOT NULL,
    kind TEXT NOT NULL,
    sent_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS outreach_log_user ON outreach_log (user, sent_at);
"""


class ChannelStore:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db
        self.db.executescript(_SCHEMA)
        self.db.commit()

    def register(self, chat_id: int, user: str) -> None:
        """A chat is one user; registering again with a new name moves the chat to that name."""
        with self.db:
            self.db.execute("DELETE FROM telegram_chats WHERE chat_id = ? OR user = ?",
                            (chat_id, user))  # fmt: skip
            self.db.execute("INSERT INTO telegram_chats (chat_id, user) VALUES (?, ?)",
                            (chat_id, user))  # fmt: skip

    def user_of(self, chat_id: int) -> str | None:
        row = self.db.execute("SELECT user FROM telegram_chats WHERE chat_id = ?", (chat_id,))
        found = row.fetchone()
        return None if found is None else found[0]

    def chat_of(self, user: str) -> int | None:
        row = self.db.execute("SELECT chat_id FROM telegram_chats WHERE user = ?", (user,))
        found = row.fetchone()
        return None if found is None else found[0]

    def chats(self) -> list[tuple[int, str]]:
        return [(c, u) for c, u in self.db.execute("SELECT chat_id, user FROM telegram_chats")]

    def seen(self, chat_id: int, at: float) -> None:
        with self.db:
            self.db.execute("UPDATE telegram_chats SET last_seen = ? WHERE chat_id = ?",
                            (at, chat_id))  # fmt: skip

    def last_seen(self, user: str) -> float | None:
        row = self.db.execute("SELECT last_seen FROM telegram_chats WHERE user = ?", (user,))
        found = row.fetchone()
        return None if found is None else found[0]

    def log_outreach(self, user: str, kind: str, at: float) -> None:
        with self.db:
            self.db.execute("INSERT INTO outreach_log (user, kind, sent_at) VALUES (?, ?, ?)",
                            (user, kind, at))  # fmt: skip

    def outreach_since(self, user: str, since: float) -> int:
        row = self.db.execute(
            "SELECT COUNT(*) FROM outreach_log WHERE user = ? AND sent_at >= ?", (user, since)
        )
        return int(row.fetchone()[0])

    def last_outreach(self, user: str) -> float | None:
        row = self.db.execute("SELECT MAX(sent_at) FROM outreach_log WHERE user = ?", (user,))
        return row.fetchone()[0]

    def outreach_count_since(self, since: float) -> int:
        row = self.db.execute("SELECT COUNT(*) FROM outreach_log WHERE sent_at >= ?", (since,))
        return int(row.fetchone()[0])
