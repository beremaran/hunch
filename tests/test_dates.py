from __future__ import annotations

from datetime import date

import pytest

from hunch.recall.dates import find_date_expressions, resolve_date

TODAY = date(2026, 10, 20)  # a Tuesday
THURSDAY = date(2026, 10, 22)
SUNDAY = date(2026, 10, 25)


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


@pytest.mark.parametrize(
    ("expr", "iso"),
    [
        ("today", "2026-10-22"),
        ("tonight", "2026-10-22"),
        ("this morning", "2026-10-22"),
        ("this afternoon", "2026-10-22"),
        ("This Evening", "2026-10-22"),
        ("tomorrow", "2026-10-23"),
        ("tomorrow night", "2026-10-23"),
        ("yesterday", "2026-10-21"),
        ("the day after tomorrow", "2026-10-24"),
        ("the day before yesterday", "2026-10-20"),
        ("Friday", "2026-10-23"),
        ("on Saturday", "2026-10-24"),
        ("next Monday", "2026-10-26"),
        ("coming Monday", "2026-10-26"),
        ("this coming Sunday", "2026-10-25"),
        ("Friday night", "2026-10-23"),
        ("Sunday morning", "2026-10-25"),
        ("Thursday", "2026-10-29"),  # today's weekday: plain and "next" mean in a week
        ("next Thursday", "2026-10-29"),
        ("this Thursday", "2026-10-22"),  # "this" means today
        ("last Thursday", "2026-10-15"),  # never today
        ("last Monday", "2026-10-19"),
        ("last Friday", "2026-10-16"),
        ("next fri", "2026-10-23"),
        ("thurs", "2026-10-29"),
        ("in 3 days", "2026-10-25"),
        ("in three days", "2026-10-25"),
        ("in a day", "2026-10-23"),
        ("in twelve days", "2026-11-03"),
        ("Dec 3", "2026-12-03"),
        ("Dec. 3", "2026-12-03"),
        ("December 3rd", "2026-12-03"),
        ("3 December", "2026-12-03"),
        ("3rd of December", "2026-12-03"),
        ("the 3rd of December", "2026-12-03"),
        ("December the 3rd", "2026-12-03"),
        ("Sept 1st", "2027-09-01"),
        ("Oct 22", "2026-10-22"),  # today counts as the next occurrence
        ("Oct 21", "2027-10-21"),
        ("Feb 29", "2028-02-29"),  # waits for the next leap year
    ],
)
def test_resolves_on_a_thursday(expr: str, iso: str) -> None:
    assert resolve_date(expr, THURSDAY) == iso


@pytest.mark.parametrize(
    ("expr", "iso"),
    [
        ("Sunday", "2026-11-01"),
        ("next Sunday", "2026-11-01"),
        ("this Sunday", "2026-10-25"),
        ("this coming Sunday", "2026-11-01"),
        ("last Sunday", "2026-10-18"),
        ("last Saturday", "2026-10-24"),
        ("Saturday", "2026-10-31"),
        ("Monday", "2026-10-26"),
        ("tomorrow", "2026-10-26"),
        ("the day before yesterday", "2026-10-23"),
        ("in 7 days", "2026-11-01"),
        ("Oct 25", "2026-10-25"),
        ("24 October", "2027-10-24"),
    ],
)
def test_resolves_on_a_sunday(expr: str, iso: str) -> None:
    assert resolve_date(expr, SUNDAY) == iso


@pytest.mark.parametrize(
    ("expr", "name"),
    [("Christmas Eve", "christmas_eve"), ("xmas eve", "christmas_eve"),
     ("Christmas Day", "christmas"), ("New Years Eve", "new_years_eve"),
     ("New Year's Day", "new_years_day"), ("Easter", "easter"), ("Easter Sunday", "easter")],
)  # fmt: skip
def test_more_holidays_stay_names(expr: str, name: str) -> None:
    assert resolve_date(expr, THURSDAY) == name


@pytest.mark.parametrize(
    "expr",
    ["last night", "next week", "next month", "next year", "in April", "in a few days", "later",
     "recently", "a while ago", "this", "Feb 30", "in zero days"],
)  # fmt: skip
def test_more_vague_or_invalid_is_none(expr: str) -> None:
    assert resolve_date(expr, THURSDAY) is None


# --- find_date_expressions ---------------------------------------------------------------------

FOUND = [
    ("See you tomorrow!", ["tomorrow"]),
    ("TOMORROW MORNING is the exam", ["TOMORROW MORNING"]),
    ("we fly the day after tomorrow", ["the day after tomorrow"]),
    ("it was the day before yesterday", ["the day before yesterday"]),
    ("day after tomorrow then", ["day after tomorrow"]),
    ("how was your day today?", ["today"]),
    ("in today's world nobody writes letters", ["today"]),
    ("Thanks for listening yesterday.", ["yesterday"]),
    ("dinner tonight?", ["tonight"]),
    ("I saw her this morning", ["this morning"]),
    ("party on Saturday", ["Saturday"]),
    ("Friday night we dance", ["Friday night"]),
    ("I went running last Monday", ["last Monday"]),
    ("next Friday is payday", ["next Friday"]),
    ("this coming Sunday at noon", ["this coming Sunday"]),
    ("this Thursday's match", ["this Thursday"]),
    ("Sunday morning brunch", ["Sunday morning"]),
    ("see you next sat", ["next sat"]),
    ("dentist on Fri", ["Fri"]),
    ("results come in 3 days", ["in 3 days"]),
    ("results come in five days time", ["in five days"]),
    ("my birthday is on Dec 3", ["Dec 3"]),
    ("my birthday is on Dec. 3, yay", ["Dec. 3"]),
    ("the gig is December 3rd", ["December 3rd"]),
    ("the gig is 3 December", ["3 December"]),
    ("the gig is 3rd of December", ["3rd of December"]),
    ("the gig is on the 3rd of December", ["the 3rd of December"]),
    ("the gig is December the 3rd", ["December the 3rd"]),
    ("Exam on 14 May.", ["14 May"]),
    ("we meet May 3rd", ["May 3rd"]),
    ("born on march 5", ["march 5"]),
    ("Christmas at my sister's again", ["Christmas"]),
    ("xmas shopping", ["xmas"]),
    ("Christmas Eve with the family", ["Christmas Eve"]),
    ("New Year's Eve party!", ["New Year's Eve"]),
    ("new years eve plans", ["new years eve"]),
    ("Easter Sunday lunch", ["Easter Sunday"]),
    ("halloween costume", ["halloween"]),
    ("Friday or Saturday?", ["Friday", "Saturday"]),
    ("I called her yesterday and we meet again next Tuesday", ["yesterday", "next Tuesday"]),
    ("Friday, Friday, gotta get down on friday", ["Friday"]),  # no duplicates
    ("Oct 31 is Halloween", ["Oct 31", "Halloween"]),
]


@pytest.mark.parametrize(("text", "exprs"), FOUND)
def test_finds_date_expressions(text: str, exprs: list[str]) -> None:
    assert find_date_expressions(text) == exprs


@pytest.mark.parametrize(
    "text",
    [
        # vague times
        "I'll call you soon", "last night was fun", "this weekend I rest", "next week maybe",
        "next month we move", "next spring", "next summer", "next year", "last year",
        "the other day I saw him", "a while ago", "recently I feel tired", "in a few days",
        "in a day or two", "in 2 days or so", "later!", "we go to Spain in April",
        "December was hard", "in December 2026",
        # weekdays used generically
        "on Fridays we swim", "every Monday I cry", "Mondays are the worst",
        "each Tuesday is the same", "We always do taco Tuesday", "Good Friday service",
        "Sunday mornings are slow", "the first Monday of the month", "it was a Friday",
        # false-positive traps
        "I may go", "I may 2 or 3 of them", "the 3 may come too", "they march on",
        "we march 5 miles", "I sat on the sofa", "the sun is out", "Wed in June",
        "wait a second", "3 cats and 2 dogs", "Jan 5 times", "February 30", "on the 3rd",
        "the day after", "I'm 31", "",
    ],
)  # fmt: skip
def test_vague_and_trap_texts_find_nothing(text: str) -> None:
    assert find_date_expressions(text) == []


@pytest.mark.parametrize(("text", "exprs"), FOUND)
def test_every_found_expression_resolves(text: str, exprs: list[str]) -> None:
    for today in (TODAY, THURSDAY, SUNDAY):
        assert all(resolve_date(e, today) is not None for e in exprs)


def test_finder_does_not_overlap_and_prefers_the_longest_match() -> None:
    assert find_date_expressions("last Monday, not Monday") == ["last Monday", "Monday"]
    assert find_date_expressions("the day after tomorrow, not tomorrow") == [
        "the day after tomorrow",
        "tomorrow",
    ]
    assert find_date_expressions("Christmas Eve, Christmas") == ["Christmas Eve", "Christmas"]


def test_two_dates_resolve_in_order() -> None:
    exprs = find_date_expressions("Flight on Friday, back on the 3rd of December.")
    assert [resolve_date(e, THURSDAY) for e in exprs] == ["2026-10-23", "2026-12-03"]
