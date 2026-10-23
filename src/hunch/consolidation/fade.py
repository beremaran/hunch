"""Nightly step 6 (Phase 7, Claude's proposal): what was said again consolidates, what was filler
fades. Like sleep: an experience repeated many times becomes one stronger memory and the single
repetitions blur; small talk and acknowledgements lose weight. Nothing is deleted, the raw log
never changes, and every change goes to the append-only trace log.

Repeats are only ever matched within one user's memories."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from hunch.config import NightlyConfig
from hunch.memory.store import MemoryStore
from hunch.pipeline.filter import content_words

_SAID = re.compile(r'^They said: "(.*)"$', re.DOTALL)
_NOT_WORD = re.compile(r"[^\w]+")


@dataclass(frozen=True, slots=True)
class FadeResult:
    survivors: int
    repeats: int
    faded: tuple[str, ...]  # memory ids whose salience went down

    def summary(self) -> dict[str, int]:
        return {"survivors": self.survivors, "repeats": self.repeats, "faded": len(self.faded)}


def said(summary: str) -> str:
    m = _SAID.match(summary)
    return m.group(1) if m else summary


def repeat_key(summary: str) -> str:
    """Two memories repeat each other when their words match, ignoring case and punctuation."""
    return _NOT_WORD.sub(" ", said(summary).casefold()).strip()


def merge_repeats(store: MemoryStore, cfg: NightlyConfig, now: float) -> FadeResult:
    """The oldest memory of each exact repeat gains `repeat_boost` per new repeat when it says
    enough to be an experience, not a routine; each new repeat fades by `filler_salience_factor`.
    Repeats merged on an earlier night are skipped."""
    done = store.repeat_ids()
    groups: dict[tuple[str, str], list] = defaultdict(list)
    for m in store.memories():
        if m.kind == "episode" and not m.suppressed and repeat_key(m.summary):
            groups[(m.owner_user, repeat_key(m.summary))].append(m)
    survivors, faded = 0, []
    for members in groups.values():
        if len(members) < 2:
            continue
        members.sort(key=lambda m: m.created_at)
        survivor, *rest = members
        new = [m for m in rest if m.id not in done]
        if not new:
            continue
        survivors += 1
        if len(content_words(said(survivor.summary))) >= cfg.repeat_boost_min_words:
            boosted = min(1.0, survivor.salience + cfg.repeat_boost * len(new))
            store.set_salience(survivor.id, boosted, "nightly: repeated experience", now)
        for m in new:
            store.set_salience(m.id, m.salience * cfg.filler_salience_factor,
                               f"nightly: repeat of {survivor.id}", now)  # fmt: skip
            store.mark_repeat(m.id, survivor.id, now)
            faded.append(m.id)
    return FadeResult(survivors, len(faded), tuple(faded))
