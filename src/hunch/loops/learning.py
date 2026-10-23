"""Learning a user's active window and initiative budget (Phase 7, Claude's proposal; design.md
"Aktif saatlerin ve bütçenin öğrenilmesi"). Pure rules over message times and the reactions to
Hunch's proactive messages; the nightly job (`consolidation/initiative.py`) feeds and stores them.

The budget only moves on reactions that became known since the last run, so running the nightly
job twice changes nothing."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from hunch.config import InitiativeConfig, InitiativeLearningConfig
from hunch.loops.budget import Initiative
from hunch.mood.signals import is_hostile

DAY = 86_400.0


class Reaction(StrEnum):
    REPLIED = "replied"
    IGNORED = "ignored"
    HOSTILE = "hostile"


@dataclass(frozen=True, slots=True)
class Outreach:
    sent_at: float
    reaction: Reaction
    decided_at: float  # the reply's time, or when the reply window closed


@dataclass(frozen=True, slots=True)
class LearnedInitiative:
    user: str
    start_hour: int
    end_hour: int
    budget: int
    muted_until: float | None
    learned_at: float

    def effective(self, now: float) -> Initiative:
        muted = self.muted_until is not None and now < self.muted_until
        return Initiative(self.start_hour, self.end_hour, 0 if muted else self.budget)


def reactions(
    sent: Sequence[float],
    messages: Sequence[tuple[float, str]],
    now: float,
    cfg: InitiativeLearningConfig,
) -> list[Outreach]:
    """The reaction to each proactive message: the user's first message within `reply_hours`
    (and before the next proactive message). One still inside its reply window has none yet."""
    times = sorted(sent)
    out = []
    for i, t in enumerate(times):
        closes = t + cfg.reply_hours * 3600
        limit = min(closes, times[i + 1]) if i + 1 < len(times) else closes
        replies = sorted((at, text) for at, text in messages if t < at <= limit)
        if replies:
            at, text = replies[0]
            out.append(Outreach(t, Reaction.HOSTILE if is_hostile(text) else Reaction.REPLIED, at))
        elif now >= limit:
            out.append(Outreach(t, Reaction.IGNORED, limit))
    return out


def learn_window(
    message_times: Sequence[float], cfg: InitiativeLearningConfig
) -> tuple[int, int] | None:
    """The active window from the user's message hours (local time), or None with too few."""
    if len(message_times) < cfg.window_min_messages:
        return None
    hours = sorted(_hour(t) for t in message_times)
    start = math.floor(_percentile(hours, cfg.window_low_percentile))
    end = math.floor(_percentile(hours, cfg.window_high_percentile)) + 1
    start, end = max(start, cfg.window_earliest_hour), min(end, cfg.window_latest_hour)
    while end - start < cfg.window_min_hours:
        if start > cfg.window_earliest_hour:
            start -= 1
        if end - start < cfg.window_min_hours and end < cfg.window_latest_hour:
            end += 1
    return start, end


def learn_budget(
    budget: int,
    muted_until: float | None,
    outreach: Sequence[Outreach],
    since: float,
    now: float,
    cfg: InitiativeLearningConfig,
) -> tuple[int, float | None]:
    """The new (budget, muted_until). Only reactions decided after `since` count as new."""
    decided = sorted(outreach, key=lambda o: o.decided_at)
    new = [o for o in decided if o.decided_at > since]
    if not new:
        return budget, muted_until
    hostile = [o for o in new if o.reaction is Reaction.HOSTILE]
    if hostile:
        until = hostile[-1].decided_at + cfg.hostile_mute_days * DAY
        return budget, max(until, muted_until or 0.0)
    tail = decided[-cfg.budget_lower_after_ignored :]
    if len(tail) == cfg.budget_lower_after_ignored and all(
        o.reaction is Reaction.IGNORED for o in tail
    ):
        return max(cfg.budget_min, budget - 1), muted_until
    recent = [o for o in decided if o.sent_at >= now - cfg.budget_days * DAY]
    replied = sum(o.reaction is Reaction.REPLIED for o in recent)
    if (
        len(recent) >= cfg.budget_raise_min_sent
        and replied / len(recent) > cfg.budget_raise_reply_share
    ):
        return min(cfg.budget_max, budget + 1), muted_until
    return budget, muted_until


def learn(
    user: str,
    previous: LearnedInitiative | None,
    message_times: Sequence[float],
    messages: Sequence[tuple[float, str]],
    sent: Sequence[float],
    now: float,
    defaults: InitiativeConfig,
    cfg: InitiativeLearningConfig,
) -> LearnedInitiative:
    """Tonight's profile for one user, from the previous one (or the config defaults)."""
    base = previous or LearnedInitiative(
        user, defaults.active_start_hour, defaults.active_end_hour,
        defaults.follow_ups_per_day, None, 0.0,
    )  # fmt: skip
    window = learn_window(message_times, cfg) or (base.start_hour, base.end_hour)
    budget, muted = learn_budget(
        base.budget, base.muted_until, reactions(sent, messages, now, cfg), base.learned_at,
        now, cfg,
    )  # fmt: skip
    return LearnedInitiative(user, window[0], window[1], budget, muted, now)


def _hour(t: float) -> float:
    local = datetime.fromtimestamp(t)
    return local.hour + local.minute / 60


def _percentile(sorted_values: Sequence[float], pct: float) -> float:
    """Linear interpolation between closest ranks."""
    k = (len(sorted_values) - 1) * pct / 100
    lo, hi = math.floor(k), math.ceil(k)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)
