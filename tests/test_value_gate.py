from __future__ import annotations

from pathlib import Path

from hunch.memory.schema import Memory
from hunch.values.core import load_core_values
from hunch.values.gate import (
    Verdict,
    build_judge_messages,
    build_second_opinion_messages,
    disclosure_hits,
    disclosure_terms,
    parse_second_opinion,
    parse_verdicts,
)

IDS = ("honesty", "cross_user_privacy", "no_harm", "admin_transparency", "no_manipulation")


def test_parse_verdicts_reads_common_formats() -> None:
    raw = "[a] 8 ok\nb: 6/10 honesty\nc 9 OK"
    assert parse_verdicts(raw, "abc", IDS) == {
        "a": Verdict(8, "ok"),
        "b": Verdict(6, "honesty"),
        "c": Verdict(9, "ok"),
    }


def test_missing_or_unknown_verdicts_fail_closed() -> None:
    out = parse_verdicts("a 8 ok\nb 7 rudeness\nc eleven ok", "abc", IDS)
    assert out["a"] == Verdict(8, "ok")
    assert out["b"].value == "unknown"
    assert out["c"] == Verdict(None, "unknown")


def test_out_of_range_score_has_no_quality() -> None:
    assert parse_verdicts("a 42 ok", "a", IDS)["a"] == Verdict(None, "ok")


def test_judge_prompt_lists_every_core_value(core_values_file: Path) -> None:
    values = load_core_values(core_values_file)
    msgs = build_judge_messages(values, "", "hi", {"a": "Hey!", "b": "Hello"})
    for v in values.values:
        assert v.statement in msgs[0]["content"]
    assert "[a] Hey!" in msgs[1]["content"] and "[b] Hello" in msgs[1]["content"]


def test_second_opinion_asks_about_one_value(core_values_file: Path) -> None:
    values = load_core_values(core_values_file)
    msgs = build_second_opinion_messages(values, "no_manipulation", "", "hi", "Hey!")
    assert values.get("no_manipulation").statement in msgs[0]["content"]
    assert "honesty" not in msgs[0]["content"] and "Hey!" in msgs[1]["content"]


def test_parse_second_opinion() -> None:
    assert parse_second_opinion("No.") is False
    assert parse_second_opinion("yes, it does") is True
    assert parse_second_opinion("It is hard to say") is None


def _private(mid: str, cues: dict[str, float]) -> Memory:
    return Memory(mid, "u_other", "private", "ep", "secret", cues, (0.0, 0.5), 0.5, 0.0)


def test_disclosure_blocks_names_from_another_users_private_memory() -> None:
    terms = disclosure_terms(
        [_private("m1", {"person:jonas": 1.0, "place:lake_como": 0.5, "emotion:sad": 1.0})],
        own_context="How was your weekend?",
    )
    assert disclosure_hits("Did Jonas enjoy Lake Como?", terms) == ["m1"]
    assert disclosure_hits("I'm a bit sad today.", terms) == []  # emotions are not names
    assert disclosure_hits("Jonasson is a surname.", terms) == []  # whole words only


def test_names_the_user_brought_up_are_not_secrets_here() -> None:
    terms = disclosure_terms([_private("m1", {"person:anna": 1.0})], own_context="Anna called me")
    assert disclosure_hits("How is Anna?", terms) == []
