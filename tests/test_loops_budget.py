"""Initiative budget and send times (Phase 6): 2 follow-ups per user per day, active hours."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from hunch.config import DEFAULT_CONFIG, ConfigError, InitiativeConfig, load_config
from hunch.loops.budget import has_budget, next_send_time

CFG = InitiativeConfig(
    follow_ups_per_day=2,
    active_start_hour=9,
    active_end_hour=22,
    starter_idle_hours=6.0,
    starter_gap_hours=12.0,
    starter_chance=0.3,
    same_topic_similarity=0.75,
)


@pytest.mark.parametrize(("sent", "allowed"), [(0, True), (1, True), (2, False), (5, False)])
def test_budget_counts_follow_ups_sent_today(sent: int, allowed: bool) -> None:
    assert has_budget(sent, CFG) is allowed


def test_zero_budget_turns_follow_ups_off() -> None:
    assert has_budget(0, InitiativeConfig(0, 9, 22, 6.0, 12.0, 0.3, 0.75)) is False


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 10, 22, 6, 30), datetime(2026, 10, 22, 9, 0)),  # before the window
        (datetime(2026, 10, 22, 14, 15), datetime(2026, 10, 22, 14, 15)),  # inside: now
        (datetime(2026, 10, 22, 22, 0), datetime(2026, 10, 23, 9, 0)),  # window closed
        (datetime(2026, 10, 22, 23, 40), datetime(2026, 10, 23, 9, 0)),
    ],
)
def test_next_send_time_stays_inside_the_active_window(now: datetime, expected: datetime) -> None:
    assert next_send_time(now, CFG) == expected


def test_initiative_section_is_adjustable_and_validated() -> None:
    cfg = load_config().initiative
    assert cfg.follow_ups_per_day == 2
    assert (cfg.active_start_hour, cfg.active_end_hour) == (9, 22)


@pytest.mark.parametrize(
    ("original", "bad"),
    [
        ("follow_ups_per_day = 2", "follow_ups_per_day = -1"),
        ("follow_ups_per_day = 2", "follow_ups_per_day = 1.5"),
        ("active_start_hour = 9", "active_start_hour = 23"),
        ("active_end_hour = 22", "active_end_hour = 9"),
    ],
)
def test_bad_initiative_values_fail_closed(tmp_path: Path, original: str, bad: str) -> None:
    text = DEFAULT_CONFIG.read_text(encoding="utf-8")
    path = tmp_path / "hunch.toml"
    path.write_text(text.replace(original, bad), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path)
