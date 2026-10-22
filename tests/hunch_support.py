"""A session where modulation materially changes the choice, so a Hunch forms (Phase 4 tests).

Lower layer: three sad, aroused memories that share only the weak emotion cue with the message
and sit between the thresholds (they are not recalled). Phase 5: they are 900 days old, since the
sad message now moves the global mood and mood congruence would lift 300-day-old ones into
reasoning. The drive leans away from warmth and
toward caution, so the hedging candidate "b" beats the warm, equally rated candidate "a".
"""

from __future__ import annotations

from hunch.memory.store import MemoryStore
from tests.fakes import FakeLLM
from tests.pipeline_support import seed_memory

WARM = "I'm sorry, that must be hard, tell me more?"
HEDGE = "Maybe wait a bit, it might be worth being careful, perhaps."
PLAIN = "Okay. What happened next?"
SOURCE_SUMMARY = 'They said: "ZEDSECRET ruined the evening at the harbour, I felt awful."'
SOURCE_CUE_VALUE = "zedsecret"


def seed_lower_layer(store: MemoryStore, owner: str = "u_berk", privacy: str = "private") -> None:
    seed_memory(store, "src0", SOURCE_SUMMARY, {"person:zedsecret": 1.0, "emotion:sad": 1.0}, 900,
                owner=owner, privacy=privacy, affect=(-0.9, 0.9), salience=0.5)  # fmt: skip
    for i in range(2):
        seed_memory(store, f"lo{i}", f"LOWER-{i}: the night everything went wrong.",
                    {"emotion:sad": 1.0}, 900, affect=(-0.9, 0.9), salience=0.4)  # fmt: skip


def hunch_llm(candidates=(WARM, HEDGE, PLAIN), judge=None) -> FakeLLM:
    return FakeLLM(
        candidates=candidates,
        cues=[{"type": "emotion", "value": "sad", "strength": 1.0}],
        judge=judge,
    )
