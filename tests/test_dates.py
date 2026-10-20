from __future__ import annotations

from datetime import date

import pytest

from hunch.recall.dates import resolve_date

TODAY = date(2026, 10, 20)  # a Tuesday


@pytest.mark.parametrize(
    ("expr", "iso"),
    [
        ("2026-11-02", "2026-11-02"),
        ("today", "2026-10-20"),
        ("tonight", "2026-10-20"),
        ("tomorrow", "2026-10-21"),
        ("tomorrow morning", "2026-10-21"),
        ("yesterday", "2026-10-19"),
        ("the day after tomorrow", "2026-10-22"),
        ("in two days", "2026-10-22"),
        ("in 5 days", "2026-10-25"),
        ("Friday", "2026-10-23"),
        ("on Friday", "2026-10-23"),
        ("this Thursday", "2026-10-22"),
        ("next Friday", "2026-10-23"),
        ("Monday", "2026-10-26"),
        ("Tuesday", "2026-10-27"),  # today is Tuesday: the next one
        ("this Tuesday", "2026-10-20"),
        ("last Sunday", "2026-10-18"),
        ("last Monday", "2026-10-19"),
        ("last Tuesday", "2026-10-13"),
        ("March 3rd", "2027-03-03"),
        ("3 March", "2027-03-03"),
        ("the 3rd of March", "2027-03-03"),
        ("Oct 31", "2026-10-31"),
        ("October 20", "2026-10-20"),
        ("Feb 14", "2027-02-14"),
        ("march_3rd", "2027-03-03"),  # the model sometimes applies the value format
        ("last_sunday", "2026-10-18"),
        ("day_after_tomorrow", "2026-10-22"),
    ],
)
def test_resolves(expr: str, iso: str) -> None:
    assert resolve_date(expr, TODAY) == iso


@pytest.mark.parametrize(
    ("expr", "name"),
    [("Christmas", "christmas"), ("Xmas", "christmas"), ("New Year's Eve", "new_years_eve"),
     ("halloween", "halloween")],
)  # fmt: skip
def test_holidays_stay_names(expr: str, name: str) -> None:
    assert resolve_date(expr, TODAY) == name


@pytest.mark.parametrize(
    "expr",
    ["soon", "last year", "next summer", "this weekend", "last spring", "lately", "the other day",
     "February 30", "2026-13-01", ""],
)  # fmt: skip
def test_vague_or_invalid_is_none(expr: str) -> None:
    assert resolve_date(expr, TODAY) is None
