"""Nightly step (Phase 7): learn each Telegram user's window and budget from the store."""

from __future__ import annotations

from datetime import datetime

from hunch.channels.store import ChannelStore
from hunch.consolidation.initiative import learn_initiatives
from hunch.memory.store import MemoryStore

NIGHT = datetime(2026, 10, 24, 0, 30).timestamp()


def _at(day: int, hour: int) -> float:
    return datetime(2026, 10, day, hour, 0).timestamp()


def test_nightly_learning_reads_the_store_and_is_idempotent(pipe_store: MemoryStore, pipe_cfg):
    channels = ChannelStore(pipe_store.db)
    channels.register(10, "berk")
    channels.register(11, "lea")
    for day in range(10, 24):
        for j, hour in enumerate((13, 15, 17)):
            pipe_store.append_turn(f"c-{day}", "berk", "user", "hi", at=_at(day, hour) + j)
    for day in (21, 22):  # after the day's messages; nothing within 6 hours: unanswered
        channels.log_outreach("berk", "memory", _at(day, 19))
    first = {p.user: p for p in learn_initiatives(pipe_store, channels, pipe_cfg, NIGHT)}
    berk, lea = first["berk"], first["lea"]
    assert (berk.start_hour, berk.end_hour) == (12, 18)  # widened around 13-17
    assert berk.budget == pipe_cfg.initiative.follow_ups_per_day - 1  # two unanswered
    assert (lea.start_hour, lea.end_hour) == (
        pipe_cfg.initiative.active_start_hour, pipe_cfg.initiative.active_end_hour,
    )  # fmt: skip
    again = {p.user: p for p in learn_initiatives(pipe_store, channels, pipe_cfg, NIGHT + 60)}
    assert again["berk"].budget == berk.budget
    assert channels.initiative("berk") == again["berk"]


def test_another_users_messages_never_shape_a_window(pipe_store: MemoryStore, pipe_cfg) -> None:
    channels = ChannelStore(pipe_store.db)
    channels.register(10, "berk")
    for day in range(10, 24):
        for hour in (2, 3, 4):
            pipe_store.append_turn(f"c-{day}", "lea", "user", "hi", at=_at(day, hour))
    (berk,) = learn_initiatives(pipe_store, channels, pipe_cfg, NIGHT)
    assert berk.start_hour == pipe_cfg.initiative.active_start_hour
