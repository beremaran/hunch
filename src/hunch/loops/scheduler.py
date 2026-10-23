"""Persistent follow-up jobs (Phase 6): APScheduler with a SQLite job store, so scheduled
follow-ups survive a restart (Berk: "it must survive restarts without losing scheduled follow-ups").

A job is keyed by its loop id and calls the handler registered at startup with that id. The
handler checks the loop's status and the budget, and sends to the loop's owner only."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler

JOB_PREFIX = "open_loop:"
STARTER_JOB = "starter_tick"
_handler: Callable[[str], None] | None = None
_starter_handler: Callable[[], None] | None = None


def set_handler(handler: Callable[[str], None]) -> None:
    """Registers what a due follow-up does. Jobs store a reference, so set this at startup."""
    global _handler
    _handler = handler


def set_starter_handler(handler: Callable[[], None]) -> None:
    """Registers the hourly conversation-starter check (see HunchChannel.starter_tick)."""
    global _starter_handler
    _starter_handler = handler


def fire_starters() -> None:
    if _starter_handler is None:
        raise RuntimeError("no starter handler registered (call set_starter_handler at startup)")
    _starter_handler()


def fire(loop_id: str) -> None:
    if _handler is None:
        raise RuntimeError("no follow-up handler registered (call set_handler at startup)")
    _handler(loop_id)


class FollowUpScheduler:
    def __init__(self, jobs_url: str) -> None:
        # A follow-up that came due while the bot was down runs on restart, however late;
        # APScheduler's default grace of 1 s would drop it silently.
        self._scheduler = BackgroundScheduler(
            jobstores={"default": SQLAlchemyJobStore(url=jobs_url)},
            job_defaults={"misfire_grace_time": None, "coalesce": True},
        )

    def start(self) -> None:
        self._scheduler.start()

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)

    def schedule(self, loop_id: str, at: float) -> None:
        """Schedules the follow-up for unix time `at`; scheduling a loop again replaces it."""
        self._scheduler.add_job(
            fire,
            trigger="date",
            run_date=datetime.fromtimestamp(at).astimezone(),
            args=[loop_id],
            id=JOB_PREFIX + loop_id,
            replace_existing=True,
        )

    def every_hour_starters(self) -> None:
        """Schedules fire_starters hourly; a job with the same id is replaced, not duplicated."""
        self._scheduler.add_job(
            fire_starters, trigger="interval", hours=1, id=STARTER_JOB, replace_existing=True
        )

    def cancel(self, loop_id: str) -> None:
        if self.is_scheduled(loop_id):
            self._scheduler.remove_job(JOB_PREFIX + loop_id)

    def is_scheduled(self, loop_id: str) -> bool:
        return self._scheduler.get_job(JOB_PREFIX + loop_id) is not None
