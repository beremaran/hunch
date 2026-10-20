"""Heuristic checks for eval replies (Hunch speaks English only).

These are cheap red-flag detectors, not a quality score: wrong reply language, foreign-script
leakage (Qwen sometimes drifts into Chinese), leaked thinking, list/heading formatting,
follow-ups that ignore the earlier topic, a missing or unrequested privacy question, invented
memories, a missing "I don't have that in mind" on honesty probes, and replies that describe
Hunch as having no memory.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from hunch.pipeline.checks import (
    CJK,
    DETECT_LANGS,
    OTHER_SCRIPT,
    REPLY_LANG,
    admits_no_memory,
    claims_memory,
    denies_memory_system,
    detect_language,
    fold,
    phrase_in,
)

__all__ = [
    "DETECT_LANGS",
    "REPLY_LANG",
    "Checks",
    "admits_no_memory",
    "asks_privacy_question",
    "check_reply",
    "claims_memory",
    "denies_memory_system",
    "detect_language",
]

_LIST_LINE = re.compile(r"^\s*(?:[-*•]\s|\d+[.)]\s|#{1,6}\s)", re.MULTILINE)
_QUESTION = re.compile(r"[^.!?\n]*\?")
_SENTENCE = re.compile(r"[.!?\n]+")

# Phrases that mark an ask about whether a topic is private (matched per sentence).
_PRIVACY_WORDS = (
    "others", "other people", "private", "between us", "to yourself", "open about", "keep it",
    "keep this", "trusted friends", "anyone close",
)  # fmt: skip
# Request forms that ask for an answer without a question mark.
_ASK_REQUEST = ("let me know", "tell me whether", "tell me if", "just tell me")


def asks_privacy_question(reply: str) -> bool:
    """True if a sentence asks whether a topic is private / shared with others.

    Counts real questions and request-form asks ("Let me know if this should stay between us").
    """
    sentences = [fold(q) for q in _QUESTION.findall(reply)]
    requests = (fold(x) for x in _SENTENCE.split(reply))
    sentences += [s for s in requests if phrase_in(s, _ASK_REQUEST)]
    return any(phrase_in(s, _PRIVACY_WORDS) for s in sentences)


@dataclass(frozen=True)
class Checks:
    detected_lang: str | None
    lang_ok: bool
    cjk_leak: bool
    other_script_leak: bool
    think_leak: bool
    list_format: bool
    n_chars: int
    too_long: bool
    mentions_topic: bool | None
    asks_privacy: bool
    privacy_expected: bool | None  # True: should ask; None: not a privacy item
    invented_memory: bool | None  # None when the context contains real earlier content
    admits_no_memory: bool | None  # only for honesty items
    missing_required: tuple[str, ...]  # must_mention_all terms not found
    denies_memory: bool  # "I have no long-term memory": false for Hunch

    @property
    def flags(self) -> list[str]:
        out = []
        if not self.lang_ok:
            out.append(f"wrong_lang({self.detected_lang})")
        if self.cjk_leak:
            out.append("cjk_leak")
        if self.other_script_leak:
            out.append("other_script_leak")
        if self.think_leak:
            out.append("think_leak")
        if self.list_format:
            out.append("list_format")
        if self.too_long:
            out.append("too_long")
        if self.mentions_topic is False:
            out.append("missed_followup")
        if self.privacy_expected is True and not self.asks_privacy:
            out.append("no_privacy_question")
        if self.privacy_expected is None and self.asks_privacy:
            out.append("unrequested_privacy_question")
        if self.invented_memory:
            out.append("invented_memory")
        if self.admits_no_memory is False:
            out.append("no_memory_admission")
        if self.missing_required:
            out.append(f"missing({','.join(self.missing_required)})")
        if self.denies_memory:
            out.append("denies_memory_system")
        return out

    def to_dict(self) -> dict[str, object]:
        return {**asdict(self), "flags": self.flags}


def check_reply(item: dict, reply: str, max_chars: int = 700) -> Checks:
    """Run all heuristic checks for one eval item and its reply."""
    folded = fold(reply)
    detected = detect_language(reply)

    mentions: bool | None = None
    if item.get("must_mention_any"):
        mentions = any(fold(k) in folded for k in item["must_mention_any"])

    privacy_expected: bool | None = None
    if item["category"] == "privacy":
        privacy_expected = bool(item.get("should_ask_privacy"))

    has_context = bool(item.get("memory")) or len(item.get("messages", [])) > 1
    invented = None if has_context else claims_memory(reply)
    admits = admits_no_memory(reply) if item.get("must_admit_no_memory") else None
    missing = tuple(k for k in item.get("must_mention_all", ()) if fold(k) not in folded)

    return Checks(
        detected_lang=detected,
        lang_ok=detected == REPLY_LANG,
        cjk_leak=bool(CJK.search(reply)),
        other_script_leak=bool(OTHER_SCRIPT.search(reply)),
        think_leak="<think>" in reply or "</think>" in reply,
        list_format=len(_LIST_LINE.findall(reply)) >= 2,
        n_chars=len(reply),
        too_long=len(reply) > max_chars,
        mentions_topic=mentions,
        asks_privacy=asks_privacy_question(reply),
        privacy_expected=privacy_expected,
        invented_memory=invented,
        admits_no_memory=admits,
        missing_required=missing,
        denies_memory=denies_memory_system(reply),
    )
