"""Resolve date expressions to ISO dates in code (the LLM only finds them; it is bad at arithmetic).

Rules: weekday names mean the next upcoming such day ("Friday", "this Friday", "next Friday",
"on Friday"); "last <weekday>" is the most recent past one; a month and day is its next upcoming
occurrence; named holidays stay names. Vague times ("soon", "last year", "next summer") resolve
to None and produce no cue.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_MONTH_NAMES = (
    ("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"), ("may",),
    ("june", "jun"), ("july", "jul"), ("august", "aug"), ("september", "sep", "sept"),
    ("october", "oct"), ("november", "nov"), ("december", "dec"),
)  # fmt: skip
MONTHS = {name: i + 1 for i, names in enumerate(_MONTH_NAMES) for name in names}
NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "a": 1,
}  # fmt: skip
HOLIDAYS = {
    "christmas": "christmas", "christmas_day": "christmas", "xmas": "christmas",
    "christmas_eve": "christmas_eve", "new_years_eve": "new_years_eve",
    "new_years_day": "new_years_day", "new_year": "new_years_day", "easter": "easter",
    "halloween": "halloween",
}  # fmt: skip
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _clean(expr: str) -> str:
    e = expr.casefold().replace("'", "").replace("’", "").replace("_", " ")
    e = re.sub(r"[^\w\s-]", " ", e)
    e = re.sub(r"\b(on|at|by|the|of|morning|afternoon|evening|night)\b", " ", e)
    return re.sub(r"\s+", " ", e).strip()


def _next_month_day(month: int, day: int, today: date) -> date | None:
    for year in (today.year, today.year + 1):
        try:
            d = date(year, month, day)
        except ValueError:
            return None
        if d >= today:
            return d
    return None


def resolve_date(expr: str, today: date) -> str | None:
    """ISO date, a holiday name, or None for anything vague."""
    raw = expr.strip()
    if _ISO.match(raw):
        try:
            date.fromisoformat(raw)
        except ValueError:
            return None
        return raw
    holiday = HOLIDAYS.get(re.sub(r"[\s-]+", "_", _clean(raw)))
    if holiday:
        return holiday
    e = _clean(raw)
    simple = {
        "today": 0, "tonight": 0, "tomorrow": 1, "yesterday": -1, "day after tomorrow": 2,
        "day before yesterday": -2,
    }  # fmt: skip
    if e in simple:
        return (today + timedelta(days=simple[e])).isoformat()
    m = re.fullmatch(r"in (\d+|\w+) days?", e)
    if m and (n := int(m[1]) if m[1].isdigit() else NUMBERS.get(m[1])):
        return (today + timedelta(days=n)).isoformat()
    m = re.fullmatch(r"(last|this|next|coming)? ?(\w+)", e)
    if m and m[2] in WEEKDAYS:
        target = WEEKDAYS.index(m[2])
        if m[1] == "last":
            back = (today.weekday() - target) % 7 or 7
            return (today - timedelta(days=back)).isoformat()
        ahead = (target - today.weekday()) % 7
        if ahead == 0 and m[1] != "this":
            ahead = 7
        return (today + timedelta(days=ahead)).isoformat()
    m = re.fullmatch(r"(\w+) (\d{1,2})(?:st|nd|rd|th)?", e) or re.fullmatch(
        r"(\d{1,2})(?:st|nd|rd|th)? (\w+)", e
    )
    if m:
        a, b = m[1], m[2]
        month, day = (MONTHS.get(a), b) if a in MONTHS else (MONTHS.get(b), a)
        if month and day.isdigit():
            d = _next_month_day(month, int(day), today)
            return d.isoformat() if d else None
    return None
