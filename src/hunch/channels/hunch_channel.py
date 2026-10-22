"""Hunch on a chat channel (Phase 6): replies to messages, follow-ups on open loops and
conversation starters that Hunch writes first, and admin commands.

Channel-agnostic: messages come in as (chat id, text) and replies go out through an injected
`send`; channels/telegram.py supplies Telegram. Everything that touches the model runs under one
lock, so one GPU job runs at a time (CLAUDE.md, test levels)."""

from __future__ import annotations

import random
import re
import threading
import time as clock_time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from hunch.channels.store import ChannelStore
from hunch.config import InitiativeConfig
from hunch.loops.budget import has_budget, in_window, next_send_time, start_of_day
from hunch.loops.outreach import Kind, OutreachResult, choose_kind
from hunch.loops.store import OpenLoop
from hunch.memory.forget import admin_forget
from hunch.pipeline.turn import Session, TurnPipeline

# Berk (Phase 6): a conversation ends after 30 minutes without a message; the next one starts fresh.
CONVERSATION_IDLE_SECONDS = 30 * 60
WELCOME = "Hi, I'm Hunch. Tell me your name with /start <name> so I know who I'm talking to."
NAME = re.compile(r"[a-z0-9_]{1,32}")
LOG_TAIL = 5
LOG_FILES = ("reflections.jsonl", "disclosures.jsonl")

Sender = Callable[[int, str], None]


class HunchChannel:
    def __init__(
        self,
        pipeline: TurnPipeline,
        channels: ChannelStore,
        cfg: InitiativeConfig,
        send: Sender,
        *,
        admin_chat_id: int | None = None,
        scheduler: object | None = None,  # FollowUpScheduler, or a test double
        log_dir: Path | None = None,
        clock: Callable[[], float] = clock_time.time,
        rng: random.Random | None = None,
        lock: threading.Lock | None = None,
    ) -> None:
        self.pipeline = pipeline
        self.loops = pipeline.loops
        self.store = pipeline.store
        self.channels = channels
        self.cfg = cfg
        self.send = send
        self.admin_chat_id = admin_chat_id
        self.scheduler = scheduler
        self.log_dir = log_dir
        self.clock = clock
        self.rng = rng or random.Random()
        self.lock = lock or threading.Lock()
        self._sessions: dict[str, tuple[Session, float]] = {}
        self._last_kind: dict[str, Kind] = {}

    # --- messages ----------------------------------------------------------------------------

    def handle_message(self, chat_id: int, text: str, now: float | None = None) -> str:
        """The reply to one message from a chat (commands included)."""
        now = self.clock() if now is None else now
        text = text.strip()
        if text.startswith("/"):
            return self._command(chat_id, text, now)
        user = self.channels.user_of(chat_id)
        if user is None:
            return WELCOME
        self.channels.seen(chat_id, now)
        session = self._session(user, now)
        with self.lock:
            result = self.pipeline.turn(session, text)
            self.pipeline.after_reply(session, result)
            new_loops = self.pipeline.extract_loops(session, result)
        self._sessions[user] = (session, now)
        for loop in new_loops:
            self._schedule(loop)
        return result.reply

    def _session(self, user: str, now: float) -> Session:
        current = self._sessions.get(user)
        if current is not None and now - current[1] < CONVERSATION_IDLE_SECONDS:
            return current[0]
        return self.pipeline.new_session(user)

    def _schedule(self, loop: OpenLoop) -> None:
        if self.scheduler is not None:
            self.scheduler.schedule(loop.id, loop.follow_up_at)  # type: ignore[attr-defined]

    # --- commands ----------------------------------------------------------------------------

    def _command(self, chat_id: int, text: str, now: float) -> str:
        word, _, arg = text.partition(" ")
        arg = arg.strip()
        if word == "/start":
            name = arg.casefold()
            if not NAME.fullmatch(name):
                return "Pick a short name, letters, digits or underscores: /start <name>"
            self.channels.register(chat_id, name)
            return f"Hi {name}! I'm Hunch. I only speak English, so let's talk in English."
        if chat_id != self.admin_chat_id:
            return "I don't know that command."
        if word == "/forget":
            return self._admin_forget(arg, now)
        if word == "/logs":
            return self._admin_logs()
        if word == "/report":
            return self._admin_report(now)
        return "I don't know that command."

    def _admin_forget(self, memory_id: str, now: float) -> str:
        if not memory_id:
            return "Usage: /forget <memory id>"
        try:
            with self.lock:
                result = admin_forget(self.store, memory_id, "telegram admin", now)
        except KeyError:
            return "No such memory (or it is already forgotten)."
        return (f"Forgotten: {len(result.memories)} memory, {len(result.derived)} derived, "
                f"{len(result.beliefs)} beliefs.")  # fmt: skip

    def _admin_logs(self) -> str:
        if self.log_dir is None:
            return "No log directory configured."
        parts = []
        for name in LOG_FILES:
            path = self.log_dir / name
            lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
            tail = "\n".join(lines[-LOG_TAIL:]) or "(empty)"
            parts.append(f"{name} (last {LOG_TAIL}):\n{tail}")
        return "\n\n".join(parts)

    def _admin_report(self, now: float) -> str:
        users = len(self.channels.chats())
        since = start_of_day(datetime.fromtimestamp(now)).timestamp()
        sent = self.channels.outreach_count_since(since)
        open_loops = self.loops.count_open()
        return f"Users: {users}. Hunch wrote first today: {sent}. Open loops: {open_loops}."

    # --- follow-ups and starters (Hunch writes first) -----------------------------------------

    def deliver_follow_up(self, loop_id: str, now: float | None = None) -> None:
        """A scheduled follow-up is due. It goes to the loop's owner only, within the budget;
        otherwise it waits for the next day's window. A loop that cannot be written is closed."""
        now = self.clock() if now is None else now
        loop = self.loops.get(loop_id)
        if loop is None or loop.status != "open" or now < loop.follow_up_at:
            return
        chat = self.channels.chat_of(loop.user)
        if chat is None:
            return  # the owner has not talked to Hunch on a chat yet; the loop waits
        if not self._has_budget(loop.user, now):
            self._postpone(loop, now)
            return
        with self.lock:
            out = self.pipeline.outreach(self._session(loop.user, now), "memory", loop)
        if out.chosen:
            self._send_outreach(loop.user, chat, out, now)
        self.loops.close(loop.id)  # sent, or nothing good could be written for it

    def starter_tick(self, now: float | None = None) -> int:
        """The hourly check (Berk, Phase 6): a starter for each quiet user, inside the active
        window, within the budget and the gap between starters. Returns how many were sent."""
        now = self.clock() if now is None else now
        if not in_window(datetime.fromtimestamp(now), self.cfg):
            return 0
        sent = 0
        for chat, user in self.channels.chats():
            seen = self.channels.last_seen(user)
            last = self.channels.last_outreach(user)
            if seen is None or now - seen < self.cfg.starter_idle_hours * 3600:
                continue
            if last is not None and now - last < self.cfg.starter_gap_hours * 3600:
                continue
            if not self._has_budget(user, now) or self.rng.random() >= self.cfg.starter_chance:
                continue
            kind = choose_kind(None, self._last_kind.get(user), self.rng)
            with self.lock:
                out = self.pipeline.outreach(self._session(user, now), kind)
            if out.chosen:
                self._send_outreach(user, chat, out, now)
                sent += 1
        return sent

    def _has_budget(self, user: str, now: float) -> bool:
        since = start_of_day(datetime.fromtimestamp(now)).timestamp()
        return has_budget(self.channels.outreach_since(user, since), self.cfg)

    def _postpone(self, loop: OpenLoop, now: float) -> None:
        tomorrow = start_of_day(datetime.fromtimestamp(now)) + timedelta(days=1)
        at = next_send_time(tomorrow, self.cfg).timestamp()
        self.loops.postpone(loop.id, at)
        if self.scheduler is not None:
            self.scheduler.schedule(loop.id, at)  # type: ignore[attr-defined]

    def _send_outreach(self, user: str, chat: int, out: OutreachResult, now: float) -> None:
        self.send(chat, out.reply)
        self.channels.log_outreach(user, out.kind, now)
        self._last_kind[user] = out.kind
