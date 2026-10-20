"""Cue extraction: parsing, validation and normalisation, with a scripted fake LLM (no GPU)."""

from __future__ import annotations

import json
from datetime import date

import pytest

from hunch.recall.cues import (
    EMOTIONS,
    build_messages,
    extract_cues,
    normalize_value,
    validate_cues,
)

TODAY = date(2026, 10, 20)


def scripted(*replies: str):
    calls: list[list[dict[str, str]]] = []
    it = iter(replies)

    def generate(messages: list[dict[str, str]]) -> str:
        calls.append(messages)
        return next(it)

    generate.calls = calls  # type: ignore[attr-defined]
    return generate


def reply(*cues: dict) -> str:
    return json.dumps({"cues": list(cues)})


@pytest.mark.parametrize(
    ("raw", "norm"),
    [
        ("Anna", "anna"),
        ("Bohemian Rhapsody", "bohemian_rhapsody"),
        ("The Martian", "the_martian"),
        ("Don't Stop Me Now!", "dont_stop_me_now"),
        ("  Central   Park ", "central_park"),
        ("Saint-Tropez", "saint-tropez"),
        ("big_mike", "big_mike"),
        ("Amélie", "amelie"),
        ("Lake Como", "lake_como"),
    ],
)
def test_normalize_value(raw: str, norm: str) -> None:
    assert normalize_value(raw) == norm


def test_valid_reply_becomes_store_cues() -> None:
    gen = scripted(
        reply(
            {"type": "person", "value": "Anna", "strength": 1.0},
            {"type": "song", "value": "Hallelujah", "strength": 0.8},
            {"type": "date", "value": "Friday", "strength": 0.4},
            {"type": "emotion", "value": "nostalgia", "strength": 0.6},
        )
    )
    out = extract_cues("Anna sang Hallelujah, see you Friday", TODAY, gen, rule_dates=False)
    assert out.cues == {
        "person:anna": 1.0,
        "song:hallelujah": 0.8,
        "date:2026-10-23": 0.4,
        "emotion:nostalgia": 0.6,
    }
    assert out.dropped == () and out.attempts == 1


@pytest.mark.parametrize(
    ("item", "reason"),
    [
        ({"type": "smell", "value": "rain"}, "unknown type"),
        ({"type": "person", "value": "  "}, "empty value"),
        ({"type": "emotion", "value": "melancholy"}, "not in vocabulary"),
        ({"type": "date", "value": "soon"}, "vague"),
        ({"type": "date", "value": "this weekend"}, "vague"),
        ({"type": "person", "value": "my mum"}, "role"),
        ({"type": "person", "value": "Little Brother"}, "role"),
        ({"type": "person", "value": "my cousins"}, "role"),
        ("anna", "not an object"),
    ],
)
def test_invalid_items_are_dropped_with_a_reason(item: object, reason: str) -> None:
    cues, dropped = validate_cues([item], TODAY)
    assert cues == {}
    assert reason in dropped[0]


def test_named_days_are_valid_dates() -> None:
    cues, _ = validate_cues([{"type": "date", "value": "Christmas"}], TODAY)
    assert cues == {"date:christmas": 0.5}


def test_limits_on_emotions_and_phrases() -> None:
    cues, dropped = validate_cues(
        [{"type": "emotion", "value": e} for e in ("joy", "pride", "excitement")]
        + [{"type": "phrase", "value": p} for p in ("taco tuesday", "the blue house")],
        TODAY,
    )
    assert [c for c in cues if c.startswith("emotion:")] == ["emotion:joy", "emotion:pride"]
    assert [c for c in cues if c.startswith("phrase:")] == ["phrase:taco_tuesday"]
    assert len(dropped) == 2


def test_strength_is_clamped_and_defaulted() -> None:
    cues, _ = validate_cues(
        [{"type": "person", "value": "ben", "strength": 7}, {"type": "place", "value": "oslo"},
         {"type": "film", "value": "dune", "strength": "high"}], TODAY,
    )  # fmt: skip
    assert cues == {"person:ben": 1.0, "place:oslo": 0.5, "film:dune": 0.5}


def test_duplicates_keep_the_strongest() -> None:
    cues, _ = validate_cues(
        [{"type": "person", "value": "Anna", "strength": 0.3},
         {"type": "person", "value": "anna", "strength": 0.9}], TODAY,
    )  # fmt: skip
    assert cues == {"person:anna": 0.9}


def test_code_fence_around_json_is_accepted() -> None:
    gen = scripted('```json\n{"cues": [{"type": "place", "value": "Lisbon"}]}\n```')
    assert extract_cues("Lisbon!", TODAY, gen).cues == {"place:lisbon": 0.5}


def test_unparseable_reply_is_retried_once() -> None:
    gen = scripted("Sure! Anna is a person.", reply({"type": "person", "value": "anna"}))
    out = extract_cues("Anna called", TODAY, gen)
    assert out.cues == {"person:anna": 0.5}
    assert out.attempts == 2 and len(out.errors) == 1


def test_two_bad_replies_give_empty_cues_not_an_error() -> None:
    gen = scripted("no json", '{"cues": "nope"}')
    out = extract_cues("Anna called", TODAY, gen)
    assert out.cues == {} and out.attempts == 2 and len(out.errors) == 2


def test_prompt_carries_today_and_the_emotion_vocabulary() -> None:
    system = build_messages("hi", TODAY)[0]["content"]
    assert "2026-10-20 (Tuesday)" in system
    assert all(e in system for e in EMOTIONS)
    assert build_messages("hi", TODAY)[1] == {"role": "user", "content": "hi"}


def test_dates_are_resolved_in_code_not_by_the_model() -> None:
    cues, _ = validate_cues(
        [{"type": "date", "value": v} for v in ("tomorrow", "last Sunday", "March 3rd")], TODAY
    )
    assert set(cues) == {"date:2026-10-21", "date:2026-10-18", "date:2027-03-03"}


def test_a_name_next_to_a_role_word_is_kept() -> None:
    cues, _ = validate_cues([{"type": "person", "value": "Aunt Rosa"}], TODAY)
    assert cues == {"person:aunt_rosa": 0.5}


def test_prompt_asks_for_date_expressions_not_arithmetic() -> None:
    system = build_messages("hi", TODAY)[0]["content"]
    assert "do not calculate" in system


# --- rule-based dates merged into the LLM cues ---------------------------------------------------


def test_rule_dates_add_what_the_llm_missed() -> None:
    gen = scripted(reply({"type": "person", "value": "Anna", "strength": 1.0}))
    out = extract_cues("Anna arrives the day after tomorrow", TODAY, gen)
    assert out.cues == {"person:anna": 1.0, "date:2026-10-22": 0.5}
    assert out.rule_dates == ("date:2026-10-22",)


@pytest.mark.parametrize(("llm_strength", "merged"), [(0.9, 0.9), (0.2, 0.5)])
def test_a_date_both_found_keeps_the_higher_strength(llm_strength: float, merged: float) -> None:
    gen = scripted(reply({"type": "date", "value": "Friday", "strength": llm_strength}))
    out = extract_cues("see you Friday", TODAY, gen)
    assert out.cues == {"date:2026-10-23": merged}
    assert out.rule_dates == ("date:2026-10-23",)


def test_two_rule_dates_and_one_key_per_resolved_day() -> None:
    gen = scripted(reply())
    out = extract_cues("Friday, Oct 23, then last Sunday's photos", TODAY, gen)
    assert out.cues == {"date:2026-10-23": 0.5, "date:2026-10-18": 0.5}
    assert out.rule_dates == ("date:2026-10-23", "date:2026-10-18")


def test_vague_times_add_no_rule_dates() -> None:
    out = extract_cues("see you soon, maybe next week", TODAY, scripted(reply()))
    assert out.cues == {} and out.rule_dates == ()


def test_rule_dates_off_measures_the_llm_alone() -> None:
    gen = scripted(reply({"type": "person", "value": "Anna"}))
    out = extract_cues("Anna arrives tomorrow", TODAY, gen, rule_dates=False)
    assert out.cues == {"person:anna": 0.5} and out.rule_dates == ()


def test_rule_dates_survive_an_unparseable_llm_reply() -> None:
    out = extract_cues("dentist on Christmas Eve", TODAY, scripted("no json", "still none"))
    assert out.cues == {"date:christmas_eve": 0.5}
    assert out.attempts == 2 and len(out.errors) == 2
