"""Open-loop extraction from one user message (design.md, "Açık döngüler ve proaktivite"; Phase 6).

A loop is something the user said they will do or is waiting for, or a reminder they asked for.
An event with a clock time ("my interview on Thursday at 2pm") gives two loops: a wish just before
it, and a question after it. The model returns JSON; this module keeps only well-formed items. The
pipeline turns each draft into OpenLoops after the reply, so extraction never adds to the latency.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from hunch.config import InitiativeConfig
from hunch.loops.budget import next_send_time
from hunch.loops.store import OpenLoop
from hunch.recall.dates import find_date_expressions, resolve_date

MAX_LOOPS = 2
MAX_DAYS = 30
MAX_TOPIC_CHARS = 120
MAX_SAID_CHARS = 300
MAX_QUESTION_CHARS = 200
# Berk (Phase 6): a wish goes an hour before a timed event; the follow-up two hours after it.
BEFORE_EVENT = timedelta(hours=1)
AFTER_EVENT = timedelta(hours=2)

EXTRACT_PROMPT = """You find open loops in one chat message a user sent: things the user said they
will do or are waiting for ("I'll see the doctor next week"), and reminders they asked for ("remind
me to call Mum on Friday"), and events with a clock time ("my interview on Thursday at 2pm"). Not
small talk, not finished events, not things only the assistant should do. Reply with JSON only, no
other text:
{"loops": [{"topic": "<2-6 words>", "user_said": "<the user's words, short>",
"question": "<one short question for later, in English, about how it went>",
"days": <whole days from today until the follow-up, 1-30>,
"time": "<HH:MM 24-hour if the user gave a clock time for the event, else null>"}]}
At most 2 loops. If there are none, reply {"loops": []}."""


@dataclass(frozen=True, slots=True)
class LoopDraft:
    topic: str
    user_said: str
    question: str
    days: int
    clock: time | None = None  # the clock time the user gave for the event, if any
    event_at: datetime | None = None  # the named day at that clock time


Generate = Callable[[list[dict[str, str]]], str]


def _text(value: object, limit: int) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned[:limit] if cleaned else None


def _clock(value: object) -> time | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value.strip(), "%H:%M").time()
    except ValueError:
        return None


def parse_drafts(raw: str) -> list[LoopDraft]:
    """The well-formed loops in the model's reply; anything else is dropped, not repaired.
    A bad or missing "time" only drops the event part: the loop itself is kept."""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match is None:
        return []
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    items = data.get("loops") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    drafts: list[LoopDraft] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        days = item.get("days")
        topic = _text(item.get("topic"), MAX_TOPIC_CHARS)
        said = _text(item.get("user_said"), MAX_SAID_CHARS)
        question = _text(item.get("question"), MAX_QUESTION_CHARS)
        if topic is None or said is None or question is None:
            continue
        if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= MAX_DAYS:
            continue
        drafts.append(LoopDraft(topic, said, question, days, clock=_clock(item.get("time"))))
        if len(drafts) == MAX_LOOPS:
            break
    return drafts


def named_day(text: str, today: date) -> date | None:
    """The one day the message names ("on Friday", "tomorrow"), from the rule-based date finder.
    The model is bad at weekday arithmetic, so a single resolvable date in the message wins."""
    resolved = {resolve_date(expr, today) for expr in find_date_expressions(text)} - {None}
    if len(resolved) != 1:
        return None
    return date.fromisoformat(resolved.pop())


def extract_drafts(text: str, generate: Generate, today: date) -> list[LoopDraft]:
    messages = [
        {"role": "system", "content": EXTRACT_PROMPT},
        {"role": "user", "content": text},
    ]
    day = named_day(text, today)
    out: list[LoopDraft] = []
    for d in parse_drafts(generate(messages)):
        days, event_at = d.days, None
        if day is not None:
            offset = (day - today).days
            if 1 <= offset <= MAX_DAYS:
                days = offset
            if 0 <= offset <= MAX_DAYS and d.clock is not None:
                event_at = datetime.combine(day, d.clock)
        out.append(LoopDraft(d.topic, d.user_said, d.question, days, d.clock, event_at))
    return out


def to_loops(
    drafts: Sequence[LoopDraft],
    user: str,
    privacy: str,
    now: float,
    cfg: InitiativeConfig,
    new_id: Callable[[], str],
) -> list[OpenLoop]:
    """Each draft becomes a loop due `days` from now, moved into the active window (budget.py).
    A timed event becomes a wish an hour before it and a follow-up two hours after it."""
    loops: list[OpenLoop] = []
    now_dt = datetime.fromtimestamp(now)
    for d in drafts:
        if d.event_at is not None:
            loops.extend(_event_loops(d, user, privacy, now, cfg, new_id, now_dt))
            continue
        due = now_dt + timedelta(days=d.days)
        at = next_send_time(due, cfg).timestamp()
        loops.append(OpenLoop(new_id(), user, d.topic, d.user_said, d.question,
                              privacy, at, created_at=now))  # fmt: skip
    return loops


def _event_loops(
    d: LoopDraft,
    user: str,
    privacy: str,
    now: float,
    cfg: InitiativeConfig,
    new_id: Callable[[], str],
    now_dt: datetime,
) -> list[OpenLoop]:
    assert d.event_at is not None
    loops: list[OpenLoop] = []
    before = d.event_at - BEFORE_EVENT
    if before > now_dt:
        wish = f"Wish the user good luck: {d.topic} is coming up at {d.event_at:%H:%M}."
        at = next_send_time(before, cfg).timestamp()
        loops.append(OpenLoop(new_id(), user, d.topic, d.user_said, wish, privacy, at,
                              created_at=now))  # fmt: skip
    after = d.event_at + AFTER_EVENT
    at = next_send_time(after, cfg).timestamp()
    loops.append(OpenLoop(new_id(), user, d.topic, d.user_said, d.question, privacy, at,
                          created_at=now))  # fmt: skip
    return loops
