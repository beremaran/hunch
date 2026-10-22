"""Persistent follow-up jobs (Phase 6): scheduled jobs survive a restart; rescheduling is safe."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from hunch.loops import scheduler
from hunch.loops.scheduler import FollowUpScheduler

FAR_FUTURE = time.time() + 30 * 86_400


def _url(tmp_path: Path) -> str:
    return f"sqlite:///{(tmp_path / 'jobs.sqlite').as_posix()}"


def test_scheduled_follow_up_survives_a_restart(tmp_path: Path) -> None:
    first = FollowUpScheduler(_url(tmp_path))
    first.start()
    first.schedule("loop-1", FAR_FUTURE)
    first.shutdown()

    second = FollowUpScheduler(_url(tmp_path))
    second.start()
    try:
        assert second.is_scheduled("loop-1")
    finally:
        second.shutdown()


def test_scheduling_the_same_loop_twice_keeps_one_job(tmp_path: Path) -> None:
    s = FollowUpScheduler(_url(tmp_path))
    s.start()
    try:
        s.schedule("loop-1", FAR_FUTURE)
        s.schedule("loop-1", FAR_FUTURE + 60)
        assert len(s._scheduler.get_jobs()) == 1
    finally:
        s.shutdown()


def test_cancel_removes_only_that_job(tmp_path: Path) -> None:
    s = FollowUpScheduler(_url(tmp_path))
    s.start()
    try:
        s.schedule("loop-1", FAR_FUTURE)
        s.schedule("loop-2", FAR_FUTURE)
        s.cancel("loop-1")
        assert not s.is_scheduled("loop-1") and s.is_scheduled("loop-2")
        s.cancel("loop-1")  # cancelling twice is harmless
    finally:
        s.shutdown()


def test_fire_calls_the_registered_handler_with_the_loop_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    monkeypatch.setattr(scheduler, "_handler", None)
    scheduler.set_handler(seen.append)
    scheduler.fire("loop-9")
    assert seen == ["loop-9"]


def test_fire_without_a_handler_fails_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scheduler, "_handler", None)
    with pytest.raises(RuntimeError):
        scheduler.fire("loop-9")
