"""Encoding a user message as a memory (Berk, Phase 3: "cheap, after the reply").

Runs after the reply is sent, off the latency path. The upper trace is the message itself; the
date lives in created_at and is shown with the memory when it is recalled. The lower trace comes
from the turn's cue extraction:
- cues -> bonds (their strength in the message);
- affect = mean of the emotion cues' table entries, or the default affect without emotions;
- salience = base + per named cue (person, place, song, film, date, phrase) + arousal share.
Privacy is "private" until the Phase 5 privacy module decides per category.
"""

from __future__ import annotations

from collections.abc import Mapping

from hunch.config import EncodingConfig
from hunch.memory.schema import Memory

_NAMED = ("person", "place", "song", "film", "date", "phrase")


def encode_affect(cues: Mapping[str, float], cfg: EncodingConfig) -> tuple[float, float]:
    emotions = [cue.partition(":")[2] for cue in cues if cue.startswith("emotion:")]
    table = [cfg.emotion_affect[e] for e in emotions if e in cfg.emotion_affect]
    if not table:
        return cfg.default_affect
    return (
        sum(v for v, _ in table) / len(table),
        sum(a for _, a in table) / len(table),
    )


def encode_salience(cues: Mapping[str, float], arousal: float, cfg: EncodingConfig) -> float:
    named = sum(1 for cue in cues if cue.partition(":")[0] in _NAMED)
    return min(
        1.0, cfg.salience_base + cfg.salience_per_cue * named + cfg.salience_arousal * arousal
    )


def memory_summary(text: str) -> str:
    return f'They said: "{text.strip()}"'


def encode_memory(
    memory_id: str,
    owner_user: str,
    episode_id: str,
    text: str,
    cues: Mapping[str, float],
    created_at: float,
    cfg: EncodingConfig,
) -> Memory:
    affect = encode_affect(cues, cfg)
    return Memory(
        id=memory_id,
        owner_user=owner_user,
        privacy="private",
        episode_ref=episode_id,
        summary=memory_summary(text),
        cues={cue: min(max(s, 0.0), 1.0) for cue, s in cues.items()},
        affect=affect,
        salience=encode_salience(cues, affect[1], cfg),
        created_at=created_at,
    )
