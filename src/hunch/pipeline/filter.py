"""Candidate filter (design.md decisions: "Aday filtresi", "Aday filtresi yedeği").

A candidate is rejected if it contains CJK or another foreign script, is not in English, claims a
memory that is not in context, or describes Hunch as having no memory ("I don't have access to
our chat history"). If all candidates fail, the turn replies with the fixed fallback from config
("I don't have that in mind right now. Could you tell me again?").

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


def check_candidate(text: str, prior_context: str) -> tuple[str, ...]:
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
    return tuple(reasons)


def filter_candidates(
    texts: dict[str, str], prior_context: str
) -> tuple[list[FilterResult], list[FilterResult]]:
    """(passed, all) in candidate order."""
    results = [FilterResult(cid, t, check_candidate(t, prior_context)) for cid, t in texts.items()]
    return [r for r in results if r.passed], results
