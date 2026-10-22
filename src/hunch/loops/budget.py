"""Initiative budget and send times (Berk, Phase 6: 2 follow-ups per user per day, adjustable in
config [initiative]; the active window is the fallback until the bot learns the user's hours)."""

from __future__ import annotations

from datetime import datetime, time, timedelta

from hunch.config import InitiativeConfig


def has_budget(sent_today: int, cfg: InitiativeConfig) -> bool:
    """True while the user has received fewer follow-ups today than the budget allows."""
    return sent_today < cfg.follow_ups_per_day


def next_send_time(now: datetime, cfg: InitiativeConfig) -> datetime:
    """The earliest moment at or after `now` inside the active window (local time)."""
    day = now.date()
    start = datetime.combine(day, time(cfg.active_start_hour))
    end = datetime.combine(day, time(cfg.active_end_hour))
    if now < start:
        return start
    if now < end:
        return now
    return start + timedelta(days=1)
