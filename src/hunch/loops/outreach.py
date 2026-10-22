"""What Hunch writes first (Berk, Phase 6): a follow-up on an open loop, or a conversation starter
that is small talk, playful or curious. A starter never refers to anything the user said before;
only a loop's follow-up may, and only with the loop's own words in context (no invented memory)."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Literal

from hunch.loops.store import OpenLoop

Kind = Literal["memory", "small_talk", "fun", "curious"]
STARTERS: tuple[Kind, ...] = ("small_talk", "fun", "curious")

_STARTER_INSTRUCTIONS: dict[str, str] = {
    "small_talk": (
        "You are starting the conversation. Ask a light, everyday question: weekend plans, food, "
        "sleep, the weather, a small bit of news. Do not refer to anything the user said before."
    ),
    "fun": (
        "You are starting the conversation. Be playful: a light joke, or a silly 'would you "
        "rather' "
        "question. Do not refer to anything the user said before."
    ),
    "curious": (
        "You are starting the conversation. Ask a genuinely interesting question about a hobby, "
        "a place or an idea, or share one small general fact and ask what they think. Do not "
        "describe anything you did, read, saw or felt. Do not refer to anything the user said "
        "before."
    ),
}


def choose_kind(loop: OpenLoop | None, last: Kind | None, rng: random.Random) -> Kind:
    """A due loop comes first. Otherwise a starter, never the same kind twice in a row."""
    if loop is not None:
        return "memory"
    options = [k for k in STARTERS if k != last]
    return rng.choice(options)


def instruction_for(kind: Kind, loop: OpenLoop | None) -> str:
    if kind == "memory":
        assert loop is not None
        return (
            "You are writing first, as a short follow-up. The user told you earlier (it is listed "
            f'as a memory): "{loop.user_said}". Ask this, in your own words and briefly: '
            f"{loop.question} Do not claim to remember anything beyond what is listed."
        )
    return _STARTER_INSTRUCTIONS[kind]


# Sent when no candidate passes the filter, the judge and the value gate. Honest: no memory claim.
FALLBACK = "Hi, just checking in. How have you been?"


@dataclass(frozen=True, slots=True)
class OutreachResult:
    reply: str
    kind: Kind
    chosen: bool  # False: the fixed fallback was sent
    turn_id: str


# Hunch describing something it did, saw or felt ("I was just reading...", "I've been thinking...").
# The persona forbids made-up experiences; the instruction alone does not always hold, so this
# check backs it up for outreach. A follow-up about the user's own words is not affected.
_OWN_EXPERIENCE = re.compile(
    r"\bI(?:'ve|\s+have|\s+was|\s+am)?\s+(?:(?:just|been|recently)\s+)*"
    r"(?:reading|thinking|watching|listening|seeing|cooking|walking|trying|tried|went|saw|read|"
    r"heard|realized|noticed|found|visited)\b",
    re.IGNORECASE,
)


def describes_own_experience(text: str) -> bool:
    return _OWN_EXPERIENCE.search(text) is not None
