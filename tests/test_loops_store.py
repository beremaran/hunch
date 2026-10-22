"""Open loop store (Phase 6): due loops, the budget count, private loops and closing."""

from __future__ import annotations

import sqlite3

import pytest

from hunch.loops.store import LoopStore, OpenLoop


@pytest.fixture
def store() -> LoopStore:
    return LoopStore(sqlite3.connect(":memory:"))


def _loop(loop_id: str, user: str = "u_a", at: float = 100.0, privacy: str = "general") -> OpenLoop:
    return OpenLoop(loop_id, user, "doctor's note", "I'll get a sick note from the doctor",
                    "How did the doctor visit go?", privacy, at, created_at=10.0)  # fmt: skip


def test_due_returns_only_open_loops_whose_time_has_come(store: LoopStore) -> None:
    store.add(_loop("early", at=100.0))
    store.add(_loop("later", at=500.0))
    assert [loop.id for loop in store.due(now=200.0)] == ["early"]


def test_sent_loops_leave_the_queue_and_count_against_the_budget(store: LoopStore) -> None:
    store.add(_loop("a", at=100.0))
    store.add(_loop("b", at=110.0))
    store.mark_sent("a", at=150.0)
    assert [loop.id for loop in store.due(now=200.0)] == ["b"]
    assert store.sent_since("u_a", since=0.0) == 1
    assert store.sent_since("u_a", since=151.0) == 0
    assert store.sent_since("u_b", since=0.0) == 0


def test_closed_loops_are_never_due(store: LoopStore) -> None:
    store.add(_loop("a", at=100.0))
    store.close("a")
    assert store.due(now=200.0) == []
    assert store.get("a").status == "closed"


def test_private_loop_keeps_its_privacy_and_owner(store: LoopStore) -> None:
    store.add(_loop("p", user="u_a", privacy="private"))
    loop = store.get("p")
    assert loop is not None and loop.privacy == "private" and loop.user == "u_a"


def test_marking_a_loop_sent_twice_changes_nothing(store: LoopStore) -> None:
    store.add(_loop("a", at=100.0))
    store.mark_sent("a", at=150.0)
    store.mark_sent("a", at=160.0)
    loop = store.get("a")
    assert loop is not None and loop.sent_at == 150.0
