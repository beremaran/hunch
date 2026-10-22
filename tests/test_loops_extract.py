"""Open-loop extraction (Phase 6): strict parsing of the model's JSON and the loop times."""

from __future__ import annotations

import json
from datetime import date, datetime, time

import pytest

from hunch.config import InitiativeConfig
from hunch.loops.extract import LoopDraft, extract_drafts, parse_drafts, to_loops

CFG = InitiativeConfig(follow_ups_per_day=2, active_start_hour=9, active_end_hour=22)


def _reply(*loops: dict) -> str:
    return json.dumps({"loops": list(loops)})


GOOD = {
    "topic": "doctor's note",
    "user_said": "I'll get a sick note from the doctor",
    "question": "How did the doctor visit go?",
    "days": 7,
}


def test_well_formed_loop_is_kept() -> None:
    assert parse_drafts(_reply(GOOD)) == [
        LoopDraft("doctor's note", "I'll get a sick note from the doctor",
                  "How did the doctor visit go?", 7)
    ]  # fmt: skip


def test_no_loops_is_an_empty_list() -> None:
    assert parse_drafts('{"loops": []}') == []


def test_prose_around_the_json_is_tolerated() -> None:
    assert len(parse_drafts("Sure! " + _reply(GOOD) + " Hope that helps.")) == 1


@pytest.mark.parametrize(
    "raw",
    [
        "not json at all",
        '{"loops": "many"}',
        '{"other": []}',
        _reply({**GOOD, "days": 0}),
        _reply({**GOOD, "days": 31}),
        _reply({**GOOD, "days": True}),
        _reply({**GOOD, "days": "7"}),
        _reply({**GOOD, "topic": "   "}),
        _reply({k: v for k, v in GOOD.items() if k != "question"}),
    ],
)
def test_malformed_items_are_dropped_not_repaired(raw: str) -> None:
    assert parse_drafts(raw) == []


def test_at_most_two_loops_per_message() -> None:
    assert len(parse_drafts(_reply(GOOD, GOOD, GOOD))) == 2


def test_long_fields_are_cut_and_whitespace_collapsed() -> None:
    draft = parse_drafts(_reply({**GOOD, "topic": "x" * 500, "user_said": "a  \n b"}))[0]
    assert len(draft.topic) == 120
    assert draft.user_said == "a b"


def test_a_named_day_in_the_message_sets_the_days_not_the_model() -> None:
    # Monday 19 Oct 2026: "on Friday" is 4 days away; the model guessed 1.
    drafts = extract_drafts(
        "Remind me to call Mum on Friday.",
        lambda _m: _reply({**GOOD, "topic": "call Mum", "days": 1}),
        date(2026, 10, 19),
    )
    assert [d.days for d in drafts] == [4]


def test_no_named_day_keeps_the_model_days() -> None:
    drafts = extract_drafts(
        "I'll get a sick note soon", lambda _m: _reply(GOOD), date(2026, 10, 19)
    )
    assert [d.days for d in drafts] == [7]


def test_extract_sends_the_user_text_to_the_model() -> None:
    seen: list[list[dict[str, str]]] = []

    def generate(messages: list[dict[str, str]]) -> str:
        seen.append(messages)
        return _reply(GOOD)

    drafts = extract_drafts("I'll see the doctor next week", generate, date(2026, 10, 19))
    assert len(drafts) == 1
    assert seen[0][-1] == {"role": "user", "content": "I'll see the doctor next week"}


def test_loop_is_due_in_the_active_window_and_keeps_privacy() -> None:
    now = datetime(2026, 10, 22, 10, 0).timestamp()
    ids = iter(["loop-a", "loop-b"])
    drafts = [LoopDraft("t", "s", "q", 1), LoopDraft("u", "s", "q", 3)]
    loops = to_loops(drafts, "u_a", "private", now, CFG, lambda: next(ids))
    assert [loop.id for loop in loops] == ["loop-a", "loop-b"]
    assert all(loop.privacy == "private" and loop.user == "u_a" for loop in loops)
    # One day later at 10:00 is already inside the window, so the time stays.
    assert datetime.fromtimestamp(loops[0].follow_up_at) == datetime(2026, 10, 23, 10, 0)
    # A draft due late at night moves to the next morning's window start.
    late = to_loops(
        [LoopDraft("v", "s", "q", 1)],
        "u_a",
        "general",
        datetime(2026, 10, 22, 23, 30).timestamp(),
        CFG,
        lambda: "loop-c",
    )
    assert datetime.fromtimestamp(late[0].follow_up_at) == datetime(2026, 10, 24, 9, 0)


def test_a_timed_event_gives_a_wish_before_and_a_question_after() -> None:
    # Monday 19 Oct 2026, 10:00. "Thursday at 2pm" is 22 Oct 14:00.
    drafts = extract_drafts(
        "My interview is on Thursday at 2pm.",
        lambda _m: _reply(
            {**GOOD, "topic": "job interview", "question": "How did it go?", "time": "14:00"}
        ),
        date(2026, 10, 19),
    )
    assert drafts[0].event_at == datetime(2026, 10, 22, 14, 0)
    loops = to_loops(
        drafts,
        "u_a",
        "general",
        datetime(2026, 10, 19, 10, 0).timestamp(),
        CFG,
        iter(["wish", "after"]).__next__,
    )
    assert [datetime.fromtimestamp(loop.follow_up_at) for loop in loops] == [
        datetime(2026, 10, 22, 13, 0),
        datetime(2026, 10, 22, 16, 0),
    ]
    assert "good luck" in loops[0].question and loops[1].question == "How did it go?"


def test_event_an_hour_away_has_no_wish_only_the_follow_up() -> None:
    drafts = [
        LoopDraft(
            "talk", "my talk", "How did it go?", 1, time(9, 30), datetime(2026, 10, 19, 9, 30)
        )
    ]
    loops = to_loops(
        drafts,
        "u_a",
        "general",
        datetime(2026, 10, 19, 9, 0).timestamp(),
        CFG,
        iter(["after"]).__next__,
    )
    assert len(loops) == 1 and loops[0].question == "How did it go?"


def test_a_bad_clock_time_keeps_the_loop_but_not_the_event() -> None:
    drafts = extract_drafts(
        "My interview is on Thursday.",
        lambda _m: _reply({**GOOD, "time": "2 in the afternoon"}),
        date(2026, 10, 19),
    )
    assert len(drafts) == 1 and drafts[0].event_at is None and drafts[0].days == 3
