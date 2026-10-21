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


# Berk (Phase 5): the second agent-written set was measured once on the frozen Phase 4 detector
# (precision 94%, recall 85%), then used to fix its gaps; it is no longer blind. Both sets are
# kept here as regressions; an honest number needs a third set.
@pytest.mark.parametrize("name", ["asks_why", "asks_why_blind2"])
def test_asks_why_probe_sets_regression(name: str) -> None:
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "eval" / "probes" / f"{name}.json"
    items = json.loads(path.read_text(encoding="utf-8"))
    wrong = [i["text"] for i in items if asks_why(i["text"]) is not i["asks_why"]]
    assert len(wrong) <= 1, wrong  # set 1 keeps one known miss ("wdym, why would that be ...")
