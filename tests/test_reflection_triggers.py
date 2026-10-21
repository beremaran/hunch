from __future__ import annotations

import pytest

from hunch.reflection.triggers import accepts_offer, asks_why


@pytest.mark.parametrize(
    "text",
    [
        "Why did you say that?",
        "why?",
        "Hmm, why",
        "What makes you think so?",
        "how come?",
        "Where's that coming from?",
        "why so cautious",
        "You seem hesitant, why?",
        "what's that based on",
        "What's your reasoning there?",
    ],
)
def test_asks_why(text: str) -> None:
    assert asks_why(text)


@pytest.mark.parametrize(
    "text",
    [
        "Why is my cat so weird today?",
        "I wonder why my boss did that.",
        "Why not, let's do it!",
        "That's why I called you.",
        "why did I even agree to this lol",
        "Do you know why the sky is blue?",
        "Anna asked me why I left early.",
    ],
)
def test_not_asks_why(text: str) -> None:
    assert not asks_why(text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Sure, think about it", True),
        ("yes please", True),
        ("Go ahead.", True),
        ("ok", True),
        ("No, it's fine", False),
        ("nah, never mind", False),
        ("Anyway, I went to the gym today and it was packed.", False),
    ],
)
def test_accepts_offer(text: str, expected: bool) -> None:
    assert accepts_offer(text) is expected
