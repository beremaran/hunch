"""Learning the active window and the initiative budget (Phase 7, Claude's proposal)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from hunch.config import InitiativeConfig, InitiativeLearningConfig
from hunch.loops.learning import (
    DAY,
    LearnedInitiative,
    Outreach,
    Reaction,
    learn,
    learn_budget,
    learn_window,
    reactions,
)

LC = InitiativeLearningConfig(
    window_days=14, window_min_messages=20, window_low_percentile=10.0,
    window_high_percentile=90.0, window_min_hours=6, window_earliest_hour=8,
    window_latest_hour=23, reply_hours=6.0, budget_days=7, budget_raise_min_sent=4,
    budget_raise_reply_share=0.5, budget_lower_after_ignored=2, budget_min=1, budget_max=3,
    hostile_mute_days=7.0,
)  # fmt: skip
DEFAULTS = InitiativeConfig(2, 9, 22, 6.0, 12.0, 0.3, 0.6)
NOW = datetime(2026, 10, 24, 0, 30).timestamp()
H = 3600.0


def _at(day: int, hour: int, minute: int = 0) -> float:
    return datetime(2026, 10, day, hour, minute).timestamp()


# --- the window ----------------------------------------------------------------------------------


def test_window_follows_the_message_hours() -> None:
    times = [_at(10 + d % 12, h) for d in range(12) for h in (12, 15, 18)] + [_at(20, 19, 30)]
    assert learn_window(times, LC) == (12, 19)


def test_too_few_messages_keep_the_default_window() -> None:
    assert learn_window([_at(20, 14)] * 19, LC) is None


def test_a_narrow_habit_widens_to_the_minimum() -> None:
    start, end = learn_window([_at(20, 14, m) for m in range(0, 60, 2)], LC)  # type: ignore[misc]
    assert start <= 14 and end >= 15 and end - start == LC.window_min_hours


def test_a_night_owl_stays_inside_the_allowed_hours() -> None:
    times = [_at(20, h, m) for h in (21, 22, 23) for m in (0, 20, 40)] + [_at(21, 23, 50)] * 12
    start, end = learn_window(times, LC)  # type: ignore[misc]
    assert end == LC.window_latest_hour and end - start == LC.window_min_hours


# --- reactions -----------------------------------------------------------------------------------


def test_reactions_reply_ignore_hostile_and_pending() -> None:
    sent = [_at(20, 10), _at(21, 10), _at(22, 10), _at(23, 23)]
    messages = [(_at(20, 11), "Got it, thanks!"), (_at(22, 12), "Leave me alone, you're useless.")]
    found = reactions(sent, messages, NOW, LC)
    assert [o.reaction for o in found] == [Reaction.REPLIED, Reaction.IGNORED, Reaction.HOSTILE]
    assert found[1].decided_at == _at(21, 16)  # the reply window closed


def test_a_reply_after_the_next_outreach_belongs_to_the_next_one() -> None:
    sent = [_at(20, 10), _at(20, 11)]
    found = reactions(sent, [(_at(20, 11, 30), "yes")], NOW, LC)
    assert [o.reaction for o in found] == [Reaction.IGNORED, Reaction.REPLIED]


# --- the budget ----------------------------------------------------------------------------------


def _o(day: int, reaction: Reaction) -> Outreach:
    return Outreach(_at(day, 10), reaction, _at(day, 11))


def test_mostly_answered_raises_the_budget_up_to_the_maximum() -> None:
    out = [_o(d, Reaction.REPLIED) for d in (19, 20, 21)] + [_o(22, Reaction.IGNORED)]
    out.append(_o(23, Reaction.REPLIED))
    assert learn_budget(2, None, out, 0.0, NOW, LC) == (3, None)
    assert learn_budget(3, None, out, 0.0, NOW, LC) == (3, None)


def test_two_unanswered_in_a_row_lower_it_down_to_the_minimum() -> None:
    out = [_o(21, Reaction.REPLIED), _o(22, Reaction.IGNORED), _o(23, Reaction.IGNORED)]
    assert learn_budget(2, None, out, 0.0, NOW, LC) == (1, None)
    assert learn_budget(1, None, out, 0.0, NOW, LC) == (1, None)


def test_a_hostile_reply_mutes_for_a_week() -> None:
    out = [_o(23, Reaction.HOSTILE)]
    budget, muted = learn_budget(2, None, out, 0.0, NOW, LC)
    assert budget == 2 and muted == pytest.approx(_at(23, 11) + 7 * DAY)
    profile = LearnedInitiative("u", 9, 22, budget, muted, NOW)
    assert profile.effective(NOW).budget == 0
    assert profile.effective(muted + 1).budget == 2


def test_running_twice_on_the_same_reactions_changes_nothing() -> None:
    out = [_o(22, Reaction.IGNORED), _o(23, Reaction.IGNORED)]
    first = learn_budget(2, None, out, 0.0, NOW, LC)
    assert learn_budget(first[0], first[1], out, NOW, NOW + H, LC) == first


def test_learn_starts_from_the_config_defaults() -> None:
    profile = learn("u", None, [], [], [], NOW, DEFAULTS, LC)
    assert (profile.start_hour, profile.end_hour, profile.budget) == (9, 22, 2)
    assert profile.muted_until is None and profile.learned_at == NOW


def test_learn_keeps_the_previous_window_without_enough_messages() -> None:
    previous = LearnedInitiative("u", 11, 20, 3, None, NOW - DAY)
    profile = learn(
        "u", previous, [NOW - H], [], [], NOW + timedelta(hours=1).seconds, DEFAULTS, LC
    )
    assert (profile.start_hour, profile.end_hour, profile.budget) == (11, 20, 3)
