"""Structural checks on eval/prompts.json so the eval set stays balanced and well-formed."""

from __future__ import annotations

import json
from collections import Counter
from itertools import pairwise
from pathlib import Path

import pytest

PROMPTS = Path(__file__).resolve().parents[1] / "eval" / "prompts.json"


@pytest.fixture(scope="module")
def data() -> dict:
    return json.loads(PROMPTS.read_text(encoding="utf-8"))


def test_about_thirty_items(data: dict) -> None:
    assert 27 <= len(data["items"]) <= 33


def test_ids_unique_and_prefixed_by_lang(data: dict) -> None:
    ids = [it["id"] for it in data["items"]]
    assert len(ids) == len(set(ids))
    for it in data["items"]:
        assert it["id"].startswith(f"{it['lang']}-{it['category']}-")


def test_balanced_per_language(data: dict) -> None:
    per_lang = Counter(it["lang"] for it in data["items"])
    assert set(per_lang) == {"tr", "de", "en"}
    assert len(set(per_lang.values())) == 1, per_lang


def test_every_language_covers_every_category(data: dict) -> None:
    cats = set(data["categories"])
    for lang in ("tr", "de", "en"):
        assert {it["category"] for it in data["items"] if it["lang"] == lang} == cats


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
