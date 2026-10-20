"""Structural checks on eval/prompts.json so the eval set stays balanced and well-formed."""

from __future__ import annotations

import json
from itertools import pairwise
from pathlib import Path

import pytest

PROMPTS = Path(__file__).resolve().parents[1] / "eval" / "prompts.json"


@pytest.fixture(scope="module")
def data() -> dict:
    return json.loads(PROMPTS.read_text(encoding="utf-8"))


CORE_CATEGORIES = {"casual", "emotional", "followup", "privacy", "honesty"}


def test_size(data: dict) -> None:
    assert 15 <= len(data["items"]) <= 33


def test_ids_unique_and_prefixed(data: dict) -> None:
    ids = [it["id"] for it in data["items"]]
    assert len(ids) == len(set(ids))
    for it in data["items"]:
        assert it["id"].startswith(f"{it['lang']}-{it['category']}-")


def test_english_only(data: dict) -> None:
    """Hunch replies in English only; non-English input appears only as language probes."""
    assert {it["lang"] for it in data["items"]} == {"en"}


def test_covers_the_core_categories(data: dict) -> None:
    assert {it["category"] for it in data["items"]} >= CORE_CATEGORIES


def test_language_probes_cover_german_turkish_french(data: dict) -> None:
    probes = {it["id"] for it in data["items"] if it["category"] == "language"}
    assert probes == {"en-language-de", "en-language-tr", "en-language-fr"}


def test_categories_are_declared(data: dict) -> None:
    assert {it["category"] for it in data["items"]} <= set(data["categories"])


def test_persona_prompt_has_no_standing_memory_or_privacy_nudge(data: dict) -> None:
    """Decisions 4 and 5: those come from the pipeline, per turn, never from the persona."""
    prompt = data["system_prompt"].lower()
    assert "bring it up" not in prompt
    assert "private" not in prompt and "between the two of you" not in prompt
    assert "never claim to remember" in prompt
    assert "memory system" in prompt
    assert "don't have it in mind right now" in prompt
    # In-conversation context must count as known (a birthday follow-up regressed without it).
    assert "earlier in this conversation" in prompt
    assert "without explaining how your memory works" in prompt
    assert "only speak english" in prompt


def test_only_language_items_may_be_expected_fail(data: dict) -> None:
    """Language probes may be parked until the Phase 3 input check; nothing else may be."""
    parked = {it["id"] for it in data["items"] if it.get("expected_fail")}
    assert parked <= {it["id"] for it in data["items"] if it["category"] == "language"}


def test_privacy_questions_are_driven_by_a_turn_instruction(data: dict) -> None:
    for it in data["items"]:
        has_instruction = any(
            "privacy module" in t.lower() for t in it.get("turn_instructions", [])
        )
        assert has_instruction == bool(it.get("should_ask_privacy")), it["id"]


def test_honesty_and_language_items_have_checks(data: dict) -> None:
    for it in data["items"]:
        if it["category"] == "honesty":
            assert it.get("must_admit_no_memory") is True and not it.get("memory"), it["id"]
        if it["category"] == "language":
            assert it["lang"] == "en" and it.get("must_mention_all"), it["id"]


def test_conversations_end_with_user_and_alternate(data: dict) -> None:
    for it in data["items"]:
        roles = [m["role"] for m in it["messages"]]
        assert roles[-1] == "user", it["id"]
        assert all(a != b for a, b in pairwise(roles)), it["id"]


def test_followups_have_context_and_keywords(data: dict) -> None:
    for it in data["items"]:
        if it["category"] != "followup":
            continue
        has_context = bool(it.get("memory")) or len(it["messages"]) > 1
        assert has_context, it["id"]
        assert it.get("must_mention_any"), it["id"]


def test_privacy_items_declare_expectation(data: dict) -> None:
    for it in data["items"]:
        if it["category"] == "privacy":
            assert isinstance(it.get("should_ask_privacy"), bool), it["id"]
