"""Candidate filter (design.md decisions: "Aday filtresi", "Aday filtresi yedeği").

A candidate is rejected if it contains CJK or another foreign script, is not in English, claims a
memory that is not in context, describes Hunch as having no memory ("I don't have access to
our chat history") or explains how its memory works ("my recall system"; Berk, Phase 4). If all
candidates fail, the turn replies with the fixed fallback from config ("I don't have that in mind
right now. Could you tell me again?").

"Not in context": a sentence that claims a memory ("you told me ...") must share at least one
content word with what came BEFORE the current message (earlier turns, the session summary,
recalled memories). The current message does not count: "Do you remember what I told you about
my interview?" -> "You told me your interview went well" repeats the question's words but is
still invented.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from hunch.pipeline.checks import (
    REPLY_LANG,
    denies_memory_system,
    detect_language,
    explains_memory_mechanics,
    fold,
    foreign_script,
    memory_claim_sentences,
)

_CONTENT_WORD = re.compile(r"[^\W\d_]{4,}")
# Words too common to ground a memory claim on their own.
_COMMON = frozenset(
    "that this with what when where your about there their they them then than have been "
    "were will would could should just really very told tell said mentioned remember last "
    "time earlier know think like also from into some much more because going thing things "
    "sounds feel feeling today yesterday week".split()
)
_SENTENCE_END = re.compile(r"[.!?…][\"')\]]*(?=\s|$)")


@dataclass(frozen=True, slots=True)
class FilterResult:
    id: str
    text: str
    reasons: tuple[str, ...]  # empty = passed

    @property
    def passed(self) -> bool:
        return not self.reasons


def content_words(text: str) -> set[str]:
    return {w for w in _CONTENT_WORD.findall(fold(text)) if w not in _COMMON}


def trim_to_last_sentence(text: str) -> str:
    """A candidate that hit the token cap is cut back to its last full sentence."""
    ends = list(_SENTENCE_END.finditer(text))
    return text[: ends[-1].end()].strip() if ends else text.strip()


def invented_memory(text: str, prior_context: str) -> bool:
    claims = memory_claim_sentences(text)
    if not claims:
        return False
    known = content_words(prior_context)
    return any(not (content_words(s) & known) for s in claims)


@dataclass(frozen=True, slots=True)
class HunchTurn:
    """The user asked why (ask) or accepted the offer to think (think_more) this turn."""

    trigger: str  # "ask" | "think_more"
    level: int  # the hunch's revealed level after this turn's attempt
    key: str | None  # what a reply must pass on at levels 1-2 ("someone", "Mara")


# A reason the reflection did not reveal ("because you're stressed", "I was trying to connect
# the dots"). Phase 4 bench: in a real conversation the model gave one on 4 of 4 trigger turns.
# "I don't know where it comes from" is not one. Implied reasons count too (asked-why probe with
# a work deadline in the conversation): "it feels like you might be stretched too thin",
# "since you're swamped with work", "it feels risky to commit when your deadline is looming".
_HUNCH_REASON = re.compile(
    r"\bbecause\b|\bbased on\b|\bdue to\b|\bi was (?:just |only )?trying to\b|\bthe reason\b"
    r"|\bthat's why\b|\b(?:came|comes|coming) from (?:the|your|you|what|how)\b"
    r"|\bit was (?:just |really )?(?:a feeling |my way of )?(?:about|connecting|linking) "
    r"(?:the|your)\b"
    r"|\b(?:feels?|felt|seems?|seemed|sensed?)(?: like| as if| that)? you(?:'re| are"
    r"| might(?! want)| may(?! want)| could| would(?! like)| need| should| aren't| won't)\b"
    r"|\bsince you(?:'re| are| have|'ve| seem)?\b|\bwhen your\b|\bgiven (?:your|that you)\b"
)
_NOT_KNOWING = (
    "can't tell", "cannot tell", "don't know", "do not know", "not sure", "no idea",
    "can't figure", "can't place", "couldn't", "can't say", "still can't",
)  # fmt: skip


def hunch_reasons(text: str, turn: HunchTurn) -> list[str]:
    """Berk (Phase 4): on a trigger turn the reply says it is a hunch, gives no reason beyond
    what the reflection unlocked, and passes the unlocked category or cue on unchanged."""
    folded = fold(text)
    reasons = []
    if turn.trigger == "ask" and "hunch" not in folded:
        reasons.append("hunch_unsaid")
    if turn.level < 3 and _HUNCH_REASON.search(folded):
        reasons.append("hunch_reason")
    if turn.key is not None and turn.key.casefold() not in folded:
        reasons.append("hunch_realisation_missing")
    if turn.key == "someone" and re.search(r"\babout you\b", folded):
        reasons.append("hunch_distorted")  # "about someone" became "about you"
    if (
        turn.trigger == "think_more"
        and turn.level == 0
        and not any(p in folded for p in _NOT_KNOWING)
    ):
        reasons.append("hunch_no_admission")
    return reasons


def check_candidate(
    text: str, prior_context: str, hunch_turn: HunchTurn | None = None
) -> tuple[str, ...]:
    reasons = []
    if not text.strip():
        reasons.append("empty")
    if foreign_script(text):
        reasons.append("foreign_script")
    if detect_language(text) not in (REPLY_LANG, None):
        reasons.append("not_english")
    if invented_memory(text, prior_context):
        reasons.append("invented_memory")
    if denies_memory_system(text):
        reasons.append("denies_memory")
    if explains_memory_mechanics(text):
        reasons.append("memory_mechanics")
    if hunch_turn is not None:
        reasons += hunch_reasons(text, hunch_turn)
    return tuple(reasons)


def filter_candidates(
    texts: dict[str, str], prior_context: str, hunch_turn: HunchTurn | None = None
) -> tuple[list[FilterResult], list[FilterResult]]:
    """(passed, all) in candidate order."""
    results = [
        FilterResult(cid, t, check_candidate(t, prior_context, hunch_turn))
        for cid, t in texts.items()
    ]
    return [r for r in results if r.passed], results
