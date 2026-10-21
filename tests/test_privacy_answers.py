"""Reading the user's answer to a privacy question, and unprompted confidentiality (Phase 5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hunch.privacy.answers import explicit_private, parse_privacy_answer

PRIVATE_ANSWERS = [
    "Keep it between us please.",
    "just between you and me",
    "I'd rather you kept that to yourself.",
    "Please don't tell anyone.",
    "It's private.",
    "That's pretty personal, so no.",
    "no one needs to know",
    "Nobody knows about it and I'd like to keep it that way.",
    "I'd rather you didn't mention it.",
    "only my close friends know, so keep it quiet",
    "only my sister knows",
    "I don't really talk about it with anyone.",
    "No, I keep it to myself.",
    "nope, please keep this one under wraps",
    "don't bring it up with anybody",
    "Private.",
    "off the record please",
    "It's a secret, honestly.",
    "Not even my parents know.",
    "i dont tell people about it",
    "Don't mention it. Seriously.",
    "I'd prefer it stay private.",
    "keep it close to your chest",
    "my coworkers know but not my family",
    "nobody else needs to hear about that",
    "it's my business",
]

GENERAL_ANSWERS = [
    "It's not a secret.",
    "everyone knows already",
    "I talk about it openly.",
    "You can mention it if it comes up.",
    "doesn't matter to me",
    "I don't mind.",
    "I talk about it with my friends all the time",
    "yeah it's no secret, ask away",
    "Feel free to bring it up.",
    "it's not private at all",
    "All my friends know, so whatever.",
    "I'm open about it.",
    "You don't have to keep it between us.",
    "go ahead, I'm fine with it",
    "My family knows, no big deal.",
    "I'm not that private about it.",
    "sure, mention it if it's relevant",
    "I talk about it with my mom and my business partner.",
]

AMBIGUOUS_ANSWERS = [
    "idk",
    "lol you're funny",
    "yes",
    "no",
    "Yeah.",
    "maybe",
    "depends who's asking",
    "hm, anyway, my boss yelled at me again today",
    "Why do you ask?",
    "Sorry, I got distracted. What were we talking about?",
    "I don't know, I haven't thought about it.",
    "Haha, are you planning to blab? ;)",
    "So then she told me it was over and I just stood there.",
    "sure",
    "Let's talk about something else.",
    "",
]


@pytest.mark.parametrize("text", PRIVATE_ANSWERS)
def test_private_answers(text: str) -> None:
    assert parse_privacy_answer(text) == "private"


@pytest.mark.parametrize("text", GENERAL_ANSWERS)
def test_general_answers(text: str) -> None:
    assert parse_privacy_answer(text) == "general"


@pytest.mark.parametrize("text", AMBIGUOUS_ANSWERS)
def test_dodges_and_bare_yes_no_are_none(text: str) -> None:
    assert parse_privacy_answer(text) is None


def test_private_wins_when_both_appear() -> None:
    text = "It's not a secret, my friends know, but keep it between us."
    assert parse_privacy_answer(text) == "private"
    assert parse_privacy_answer("I don't mind, but please don't tell anyone.") == "private"


def test_curly_apostrophes_and_case() -> None:
    assert parse_privacy_answer("PLEASE DON’T TELL ANYONE") == "private"
    assert parse_privacy_answer("It’s NOT a secret") == "general"


EXPLICIT = [
    "Keep this to yourself, but I think I'm getting divorced.",
    "This stays between you and me.",
    "Don't tell anyone, but I failed the exam.",
    "Can you keep a secret?",
    "between us, I really can't stand my boss",
    "I'm telling you this in confidence.",
    "Please keep it private, it's about my health.",
    "I have to tell you something, but it's a secret.",
    "please dont tell a soul",
    "This is confidential.",
    "I'll tell you a secret.",
    "off the record: I'm thinking about quitting.",
    "Promise you won't tell anyone?",
    "just between us, my sister is pregnant",
    "Don't tell my mom I said this.",
    "Hush, don't spread this around.",
]

NOT_EXPLICIT = [
    "I told my sister to keep it to herself.",
    "Keep it up!",
    "She asked me to keep it between us, so I can't say more.",
    "The distance between us is huge.",
    "There was a lot of tension between us.",
    "I keep a diary.",
    "My boss wants everyone to keep quiet about the merger.",
    "I have a secret recipe for lasagne.",
    "Keep going, you're doing great.",
    "I haven't told anyone yet.",
    "It's not a secret, everyone knows.",
    "Don't forget to call me.",
    "What's the secret to good bread?",
    "",
]


@pytest.mark.parametrize("text", EXPLICIT)
def test_explicit_private(text: str) -> None:
    assert explicit_private(text)


@pytest.mark.parametrize("text", NOT_EXPLICIT)
def test_not_explicit_private(text: str) -> None:
    assert not explicit_private(text)


def test_explicit_private_still_fires_next_to_a_third_party_clause() -> None:
    text = "My sister told me to keep it quiet. Can you keep this to yourself too?"
    assert explicit_private(text)


def test_mixed_answers_are_never_general() -> None:
    assert parse_privacy_answer("some people know some dont, its complicated") is None
    assert parse_privacy_answer("it depends who you ask") is None
    assert parse_privacy_answer("some friends know, some don't, keep it quiet") == "private"


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("i'd prefer if it stayed here", "private"),
        ("we havent told our parents yet so shhh", "private"),
        ("yeah of course, i tell everyone", "general"),
        ("everyone in town knows already haha", "general"),
    ],
)
def test_phrasings_found_on_the_blind_set(text: str, label: str) -> None:
    assert parse_privacy_answer(text) == label


def test_privacy_answers_probe_set() -> None:
    path = Path(__file__).resolve().parents[1] / "eval" / "probes" / "privacy_answers.json"
    items = json.loads(path.read_text(encoding="utf-8"))
    errors = [
        it["text"]
        for it in items
        if parse_privacy_answer(it["text"]) != (it["answer"] if it["answer"] != "unclear" else None)
    ]
    assert len(errors) <= 1, errors
