"""Initiative budget and send times (Berk, Phase 6: 2 follow-ups per user per day, adjustable in
config [initiative]; the active window is the fallback until the bot learns the user's hours).
Phase 7: the nightly job learns a window and a budget per user (`loops/learning.py`)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from hunch.config import InitiativeConfig


@dataclass(frozen=True, slots=True)
class Initiative:
    """One user's active window (local hours, end exclusive) and daily budget."""

    start_hour: int
    end_hour: int
    budget: int

    @classmethod
    def default(cls, cfg: InitiativeConfig) -> Initiative:
        return cls(cfg.active_start_hour, cfg.active_end_hour, cfg.follow_ups_per_day)


def has_budget(sent_today: int, initiative: Initiative) -> bool:
    """True while the user has received fewer proactive messages today than the budget allows."""
    return sent_today < initiative.budget


def next_send_time(now: datetime, initiative: Initiative) -> datetime:
    """The earliest moment at or after `now` inside the active window (local time)."""
    day = now.date()
    start = datetime.combine(day, time(initiative.start_hour))
    end = datetime.combine(day, time(initiative.end_hour))
    if now < start:
        return start
    if now < end:
        return now
    return start + timedelta(days=1)


def in_window(now: datetime, initiative: Initiative) -> bool:
    """True when `now` (local time) is inside the active window."""
    day = now.date()
    return (
        datetime.combine(day, time(initiative.start_hour))
        <= now
        < datetime.combine(day, time(initiative.end_hour))
    )


def start_of_day(now: datetime) -> datetime:
    return datetime.combine(now.date(), time(0))
