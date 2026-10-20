"""Find date expressions in a message and resolve them to ISO dates in code.

The LLM is bad at arithmetic and misses many dates, so detection has a rule-based path too:
`find_date_expressions` scans the raw text (no `today` needed) and `resolve_date` turns each
expression into a date.

Rules: weekday names mean the next upcoming such day ("Friday", "this Friday", "next Friday",
"on Friday"; on that weekday itself plain and "next" mean in a week, "this" means today);
"last <weekday>" is the most recent past one; a month and day is its next occurrence on or after
today; named holidays stay names. Vague times ("soon", "last year", "next summer", "on Fridays")
resolve to None, are not found, and produce no cue.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date, timedelta

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
# Abbreviations that are also ordinary words ("sat", "sun", "wed", "mon") are only found after
# last/this/next/coming; the others are found alone too.
_WEEKDAY_ABBR = {
    "mon": 0, "tue": 1, "tues": 1, "wed": 2, "weds": 2, "thu": 3, "thur": 3, "thurs": 3,
    "fri": 4, "sat": 5, "sun": 6,
}  # fmt: skip
_AMBIGUOUS_ABBR = ("mon", "wed", "sat", "sun")
WEEKDAY_INDEX = {name: i for i, name in enumerate(WEEKDAYS)} | _WEEKDAY_ABBR
_MONTH_NAMES = (
    ("january", "jan"), ("february", "feb"), ("march", "mar"), ("april", "apr"), ("may",),
    ("june", "jun"), ("july", "jul"), ("august", "aug"), ("september", "sep", "sept"),
    ("october", "oct"), ("november", "nov"), ("december", "dec"),
)  # fmt: skip
MONTHS = {name: i + 1 for i, names in enumerate(_MONTH_NAMES) for name in names}
NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "a": 1,
}  # fmt: skip
HOLIDAYS = {
    "christmas": "christmas", "christmas_day": "christmas", "xmas": "christmas",
    "xmas_day": "christmas", "christmas_eve": "christmas_eve", "xmas_eve": "christmas_eve",
    "new_years_eve": "new_years_eve", "new_year_eve": "new_years_eve",
    "new_years_day": "new_years_day", "new_year_day": "new_years_day", "new_year": "new_years_day",
    "easter": "easter", "easter_sunday": "easter", "halloween": "halloween",
}  # fmt: skip
_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _clean(expr: str) -> str:
    e = expr.casefold().replace("'", "").replace("’", "").replace("_", " ")
    e = re.sub(r"[^\w\s-]", " ", e)
    e = re.sub(r"\b(on|at|by|the|of|morning|afternoon|evening|night)\b", " ", e)
    return re.sub(r"\s+", " ", e).strip()


def _valid_month_day(month: int, day: int) -> bool:
    try:
        date(2000, month, day)  # a leap year, so February 29 counts
    except ValueError:
        return False
    return True


def _next_month_day(month: int, day: int, today: date) -> date | None:
    if not _valid_month_day(month, day):
        return None
    for year in range(today.year, today.year + 9):  # February 29 waits for a leap year
        try:
            d = date(year, month, day)
        except ValueError:
            continue
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
    if re.fullmatch(r"this[\s_]+(morning|afternoon|evening)", raw.casefold()):
        return today.isoformat()
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
    m = re.fullmatch(r"(last|this coming|this|next|coming)? ?(\w+)", e)
    if m and m[2] in WEEKDAY_INDEX:
        target = WEEKDAY_INDEX[m[2]]
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


# --- Detection ---------------------------------------------------------------------------------


def _alt(words: Iterable[str]) -> str:
    """Regex alternation, longest first so "sept" wins over "sep"."""
    return "|".join(sorted((re.escape(w) for w in words), key=len, reverse=True))


_TOD = r"(?:\s+(?:morning|afternoon|evening|night)\b)?"
_WD_ALL = _alt([*WEEKDAYS, *_WEEKDAY_ABBR])
_WD_ALONE = _alt([*WEEKDAYS, *(a for a in _WEEKDAY_ABBR if a not in _AMBIGUOUS_ABBR)])
_MON = rf"(?:{_alt(MONTHS)})"
_DAY = r"(?:3[01]|[12]\d|0?[1-9])(?:st|nd|rd|th)?"
_APOS = r"['’]?"

# Alternatives that can start at the same position are ordered longest first; finditer then
# returns leftmost, non-overlapping matches ("last Monday" starts before "Monday").
_FINDER = re.compile(
    rf"""\b(?:
        (?P<holiday>(?:christmas|xmas)\s+(?:eve|day)|christmas|xmas
            |new\s+year(?:{_APOS}s)?\s+(?:eve|day)|easter\s+sunday|easter|halloween)
      | (?P<relative>(?:the\s+)?day\s+(?:after\s+tomorrow|before\s+yesterday)
            |this\s+(?:morning|afternoon|evening)|today|tonight|(?:tomorrow|yesterday){_TOD})
      | (?P<in_days>in\s+(?:\d{{1,3}}|{_alt(NUMBERS)})\s+days?)
      | (?P<weekday>(?:(?:last|next|this\s+coming|this|coming)\s+(?:{_WD_ALL})
            |(?:{_WD_ALONE})){_TOD})
      | (?P<month_first>{_MON}\.?\s+(?:the\s+)?(?P<d1>{_DAY}))
      | (?P<day_first>(?:the\s+)?(?P<d2>{_DAY})\s+(?:of\s+)?{_MON})
    )\b""",
    re.IGNORECASE | re.VERBOSE,
)
# A weekday after one of these is generic or part of a name ("every Monday", "Good Friday",
# "taco Tuesday").
_GENERIC_BEFORE = re.compile(
    r"\b(?:every|each|other|a|any|some|most|all|first|second|third|fourth|final|good|black"
    r"|cyber|super|ash|easter|blue|palm|holy|maundy|taco|throwback|casual|meatless|manic|wine"
    r"|fun|lazy)\s+$",
    re.IGNORECASE,
)
_GENERIC_AFTER = re.compile(
    r"^(?:\s+(?:mornings|afternoons|evenings|nights|funday)\b|\s+of\s+(?:the|every|each)\b)",
    re.IGNORECASE,
)
# "in a day or two", "in 3 days or so" are vague.
_OR_AFTER = re.compile(r"^\s+or\b", re.IGNORECASE)
# "march 5 miles", "Jan 5 times": a number that counts something, not a day of the month.
_UNIT_AFTER = re.compile(
    r"^\s+(?:times|miles|km|kms|kilometers|kilometres|meters|metres|minutes|mins|hours|hrs"
    r"|days|weeks|months|years|people|percent|points|pounds|kg|kilos|euros|dollars|bucks)\b",
    re.IGNORECASE,
)
# "the 3 may come", "I may 2": "may" or "march" used as a verb.
_VERB_MONTHS = ("may", "march", "mar")
_SUBJECT_BEFORE = re.compile(r"\b(?:i|you|we|they|he|she|it|who|that|which|there)\s+$", re.I)
_VERB_AFTER = re.compile(
    r"^\s+(?:be|have|not|go|come|need|want|get|take|also|well|never|still|just|try|see|help"
    r"|make|do|find|know|look|feel|end|on|to|into|in|through|down|up|along|past|off|forward)\b",
    re.IGNORECASE,
)


def _month_day_ok(m: re.Match[str], before: str, after: str) -> bool:
    text = m[0]
    words = re.findall(r"[a-z]+", text.casefold())
    month = next(w for w in words if w in MONTHS)
    day = int(re.match(r"\d+", m["d1"] or m["d2"])[0])  # type: ignore[index]
    if not _valid_month_day(MONTHS[month], day) or _UNIT_AFTER.match(after):
        return False
    if month not in _VERB_MONTHS:
        return True
    if m["month_first"]:
        return not _SUBJECT_BEFORE.search(before)
    bare_number_first = not re.search(r"(st|nd|rd|th)\b|\bof\b", text, re.I)
    return not (bare_number_first and _VERB_AFTER.match(after))


def find_date_expressions(text: str) -> list[str]:
    """Date expressions in a raw message, as substrings that `resolve_date` resolves.

    Order of appearance, no duplicates, no overlaps, longest match ("the day after tomorrow",
    not "tomorrow"). Detection only: does not depend on today's date.
    """
    found: list[str] = []
    seen: set[str] = set()
    for m in _FINDER.finditer(text):
        before, after = text[: m.start()], text[m.end() :]
        if m["weekday"] and (_GENERIC_BEFORE.search(before) or _GENERIC_AFTER.match(after)):
            continue
        if m["in_days"] and _OR_AFTER.match(after):
            continue
        if (m["month_first"] or m["day_first"]) and not _month_day_ok(m, before, after):
            continue
        key = re.sub(r"\s+", " ", m[0].casefold())
        if key not in seen:
            seen.add(key)
            found.append(m[0])
    return found
