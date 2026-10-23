"""Nightly step 6b (Phase 7, Claude's proposal): the day's memories are labelled filler or
meaningful by the model, and filler fades (salience x `filler_salience_factor`); nothing is
deleted. Like sleep: small talk leaves little trace, what told something about a person stays.

A memory is judged on its own first. What Hunch said just before can only rescue it, as a
person would hear it: "yes" alone is filler, "yes" to "Did you get the job?" is not. Context
never condemns: on the live data, a long reply before "Ill be unemployed in November. I have to
go now" made the model call the whole message a sign-off. Only a clear "filler" fades a memory;
losing something meaningful costs more than keeping a "hey". Each memory is labelled once."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from hunch.config import NightlyConfig
from hunch.consolidation.fade import said
from hunch.memory.store import MemoryStore

Generate = Callable[[list[dict[str, str]]], str]

FILLER_PROMPT = """You sort what a user wrote to a chatbot into two kinds. "filler": greetings and
sign-offs, acknowledgements and reactions that carry no information (ok, thanks, haha, nice), and
small talk about the chatbot itself (are you there, what can you do, what is your name, do you
remember me). "meaningful": anything that tells something about the user or their life: people
they know, plans, events, feelings, opinions, preferences, or a real request or topic. If the
message answers what the chatbot just said, judge the answer together with that question.
Answer with exactly one word: filler or meaningful."""
FILLER_MAX_NEW_TOKENS = 4


@dataclass(frozen=True, slots=True)
class FillerResult:
    labelled: int
    faded: tuple[str, ...]

    def summary(self) -> dict[str, int]:
        return {"labelled": self.labelled, "faded": len(self.faded)}


def build_filler_messages(message: str, before: str | None) -> list[dict[str, str]]:
    context = f"The chatbot had just said: {before}\n" if before else ""
    return [
        {"role": "system", "content": FILLER_PROMPT},
        {"role": "user", "content": f"{context}The user wrote: {message}"},
    ]


def parse_filler(raw: str) -> bool:
    """Only a clear "filler" fades a memory. "small talk" is the prompt's own word for it; the
    model answered that on 2 of 60 filler items in the blind set (reports/phase7/REPORT.md §4)."""
    return re.match(r"\W*(?:filler|small talk)\b", raw.casefold()) is not None


def label_filler(
    store: MemoryStore, generate: Generate, cfg: NightlyConfig, since: float, now: float
) -> FillerResult:
    done = store.labelled_ids() | store.repeat_ids()
    labelled, faded = 0, []
    for m in store.memories():
        if m.kind != "episode" or m.suppressed or m.created_at < since or m.id in done:
            continue
        text = said(m.summary)
        filler = parse_filler(generate(build_filler_messages(text, None)))
        if filler and (before := store.said_before(m)) is not None:
            filler = parse_filler(generate(build_filler_messages(text, before)))
        store.label_memory(m.id, "filler" if filler else "meaningful", now)
        labelled += 1
        if filler:
            store.set_salience(m.id, m.salience * cfg.filler_salience_factor,
                               "nightly: filler", now)  # fmt: skip
            faded.append(m.id)
    return FillerResult(labelled, tuple(faded))
