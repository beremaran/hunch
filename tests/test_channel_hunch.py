"""Hunch on a chat channel (Phase 6): chats and names, conversations, follow-ups within the budget,
conversation starters, owner-only delivery and the admin commands. Fake model, no GPU."""

from __future__ import annotations

from datetime import datetime

import pytest

from hunch.channels.hunch_channel import CONVERSATION_IDLE_SECONDS, HunchChannel
from hunch.channels.store import ChannelStore
from hunch.loops.store import OpenLoop
from tests.fakes import FakeLLM, HashEmbedder
from tests.pipeline_support import DIM

MORNING = datetime(2026, 10, 22, 10, 0).timestamp()
NIGHT = datetime(2026, 10, 22, 23, 30).timestamp()
PLAIN = ("Quick one: what are you up to this weekend?",) * 3


class Recorder:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    def __call__(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


class Scheduled:
    def __init__(self) -> None:
        self.jobs: dict[str, float] = {}

    def schedule(self, loop_id: str, at: float) -> None:
        self.jobs[loop_id] = at


@pytest.fixture
def channel(make, pipe_store, pipe_cfg, monkeypatch, tmp_path):
    llm = FakeLLM(candidates=PLAIN)
    pipe = make(llm, HashEmbedder(DIM))
    monkeypatch.setattr(pipe, "extract_loops", lambda session, result: [])  # no model call
    rec = Recorder()
    ch = HunchChannel(
        pipe, ChannelStore(pipe_store.db), pipe_cfg.initiative, rec,
        admin_chat_id=1, scheduler=Scheduled(), log_dir=tmp_path, clock=lambda: MORNING,
        rng=__import__("random").Random(4),
    )  # fmt: skip
    ch.recorder = rec
    ch.llm = llm
    return ch


def _loop(loop_id: str, user: str, at: float) -> OpenLoop:
    return OpenLoop(loop_id, user, "job interview", "my interview is on Thursday at 2pm",
                    "How did the interview go?", "general", at, created_at=MORNING)  # fmt: skip


def test_unknown_chat_gets_the_welcome_and_start_registers_a_name(channel) -> None:
    assert "chat id is 10" in channel.handle_message(10, "hello")
    assert "Hi berk" in channel.handle_message(10, "/start Berk", now=MORNING)
    assert channel.channels.user_of(10) == "berk"


def test_invalid_names_are_refused(channel) -> None:
    assert "Pick a short name" in channel.handle_message(10, "/start two words", now=MORNING)
    assert channel.channels.user_of(10) is None


def test_a_registered_chat_gets_a_reply_and_the_turn_is_stored(channel, pipe_store) -> None:
    channel.handle_message(10, "/start berk", now=MORNING)
    reply = channel.handle_message(10, "Good morning Hunch", now=MORNING)
    assert reply in PLAIN
    assert [t.role for t in pipe_store.turns(channel._sessions["berk"][0].conversation_id)] == [
        "user", "assistant"]  # fmt: skip


def test_a_quiet_conversation_ends_after_thirty_minutes(channel) -> None:
    channel.handle_message(10, "/start berk", now=MORNING)
    first = channel.handle_message(10, "Hello", now=MORNING)
    first_id = channel._sessions["berk"][0].conversation_id
    channel.handle_message(10, "Still here", now=MORNING + 60)
    assert channel._sessions["berk"][0].conversation_id == first_id
    channel.handle_message(10, "Back again", now=MORNING + CONVERSATION_IDLE_SECONDS + 60)
    assert channel._sessions["berk"][0].conversation_id != first_id
    assert first  # the first reply was a normal reply


def test_due_follow_up_goes_to_the_owner_and_closes_the_loop(channel) -> None:
    channel.handle_message(10, "/start berk", now=MORNING)
    channel.loops.add(_loop("l1", "berk", MORNING - 60))
    channel.deliver_follow_up("l1", now=MORNING)
    assert channel.recorder.sent and channel.recorder.sent[0][0] == 10
    assert channel.loops.get("l1").status == "closed"


def test_follow_up_is_not_sent_before_its_time(channel) -> None:
    channel.handle_message(10, "/start berk", now=MORNING)
    channel.loops.add(_loop("l1", "berk", MORNING + 3600))
    channel.deliver_follow_up("l1", now=MORNING)
    assert channel.recorder.sent == [] and channel.loops.get("l1").status == "open"


def test_a_private_loop_never_goes_to_another_chat(channel) -> None:
    channel.handle_message(10, "/start berk", now=MORNING)
    channel.handle_message(11, "/start lea", now=MORNING)
    channel.loops.add(_loop("l1", "berk", MORNING - 60))
    channel.deliver_follow_up("l1", now=MORNING)
    assert all(chat == 10 for chat, _ in channel.recorder.sent)


def test_budget_postpones_the_third_follow_up_to_tomorrow(channel, pipe_cfg) -> None:
    channel.handle_message(10, "/start berk", now=MORNING)
    for i in range(pipe_cfg.initiative.follow_ups_per_day):
        channel.loops.add(_loop(f"ok{i}", "berk", MORNING - 60))
        channel.deliver_follow_up(f"ok{i}", now=MORNING)
    channel.loops.add(_loop("late", "berk", MORNING - 60))
    channel.deliver_follow_up("late", now=MORNING)
    assert len(channel.recorder.sent) == pipe_cfg.initiative.follow_ups_per_day
    loop = channel.loops.get("late")
    assert loop.status == "open"
    assert datetime.fromtimestamp(loop.follow_up_at) == datetime(2026, 10, 23, 9, 0)
    assert channel.scheduler.jobs["late"] == loop.follow_up_at


def test_starter_goes_to_a_quiet_user_inside_the_window(channel, pipe_cfg) -> None:
    channel.handle_message(10, "/start berk", now=MORNING - 10 * 3600)
    channel._sessions.clear()
    channel.channels.seen(10, MORNING - 10 * 3600)
    channel.rng.random = lambda: 0.0  # the chance check always passes
    assert channel.starter_tick(now=MORNING) == 1
    assert channel.recorder.sent[0][0] == 10


def test_no_starter_outside_the_window_or_for_a_chatty_user(channel) -> None:
    channel.handle_message(10, "/start berk", now=MORNING)
    channel.channels.seen(10, MORNING - 3600)
    channel.rng.random = lambda: 0.0
    assert channel.starter_tick(now=NIGHT) == 0
    assert channel.starter_tick(now=MORNING) == 0  # seen an hour ago: not quiet enough


def test_starter_gap_is_respected(channel) -> None:
    channel.handle_message(10, "/start berk", now=MORNING - 20 * 3600)
    channel.channels.seen(10, MORNING - 20 * 3600)
    channel.rng.random = lambda: 0.0
    assert channel.starter_tick(now=MORNING) == 1
    assert channel.starter_tick(now=MORNING + 3600) == 0  # less than starter_gap_hours later


def test_admin_commands_are_for_the_admin_chat_only(channel) -> None:
    channel.handle_message(10, "/start berk", now=MORNING)
    assert channel.handle_message(10, "/report", now=MORNING) == "I don't know that command."
    assert channel.handle_message(1, "/report", now=MORNING).startswith("Users: 1.")
    assert "No such memory" in channel.handle_message(1, "/forget nope", now=MORNING)
    assert "(empty)" in channel.handle_message(1, "/logs", now=MORNING)
