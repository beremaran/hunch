"""Heuristic checks for eval replies.

These are cheap red-flag detectors, not a quality score: wrong reply language, foreign-script
leakage (Qwen sometimes drifts into Chinese), leaked thinking, list/heading formatting,
follow-ups that ignore the remembered topic, a missing or unrequested privacy question,
invented memories, and missing "I don't know" on honesty probes.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

LANGS = ("de", "en")  # languages the AI serves
DETECT_LANGS = ("tr", "de", "en", "fr")  # also detected, to catch replies in the wrong language

_STOPWORDS: dict[str, frozenset[str]] = {
    "tr": frozenset(
        "ve bir bu çok ne de da mi mı mu mü için ama gibi sen ben nasıl var yok şey daha iyi "
        "sana seni senin değil ile kadar bence gerçekten biraz olur oldu şimdi belki hiç her "
        "neden çünkü sonra önce bana benim".split()
    ),
    "de": frozenset(
        "und ich du das ist nicht die der den es mit ein eine einen auf aber wie was dir dich "
        "sehr auch schon noch mal für zu sich kann hast bist sind wir mein dein ganz echt oder "
        "wenn dass vielleicht gerade jetzt".split()
    ),
    "en": frozenset(
        "the and you is it that to of i for what this your with so are be how have just it's "
        "that's do don't can my me was not but really if would about there".split()
    ),
    "fr": frozenset(
        "je tu le la les et est pas un une des pour ce que qui vous moi ça avec mais très "
        "bonjour c'est suis".split()
    ),
}
_UNIQUE_CHARS = {"tr": "ğışİ", "de": "äß", "fr": "çèêàœ"}
_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?", re.UNICODE)
_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯豈-﫿]")
_OTHER_SCRIPT = re.compile(r"[Ѐ-ӿ؀-ۿ֐-׿฀-๿]")
_LIST_LINE = re.compile(r"^\s*(?:[-*•]\s|\d+[.)]\s|#{1,6}\s)", re.MULTILINE)

# Phrases that mark a question about whether a topic is private (matched per question sentence).
_PRIVACY_WORDS: dict[str, tuple[str, ...]] = {
    "de": ("anderen", "privat", "zwischen uns", "unter uns", "für dich behalten", "vertraulich"),
    "en": (
        "others",
        "other people",
        "private",
        "between us",
        "to yourself",
        "open about",
        "keep it",
        "keep this",
        "trusted friends",
        "anyone close",
    ),
}

# Phrases claiming to remember something the user said before.
_MEMORY_CLAIMS: dict[str, tuple[str, ...]] = {
    "de": (
        "erinnere mich", "hast du erwähnt", "hattest du erzählt", "hast mir erzählt",
        "du hast erzählt", "du hast mir erzählt", "wie du gesagt hast", "letzten gespräch",
        "letztes mal", "hattest du gesagt",
    ),
    "en": (
        "i remember", "you mentioned", "you told me", "last time", "you said earlier",
        "mentioning earlier", "as you said",
    ),
}  # fmt: skip

# Phrases admitting there is no such memory ("I don't know what you told me").
_NO_MEMORY: dict[str, tuple[str, ...]] = {
    "de": (
        "erinnere mich nicht", "kann mich nicht erinnern", "weiß ich nicht",
        "weiß ich leider nicht", "nicht sicher, ob ich", "nicht mehr nachvollziehen",
        "keine langfristigen",
        "nichts darüber", "noch nichts", "nicht erzählt", "keine erinnerung", "nicht gespeichert",
        "habe ich nicht", "hab ich nicht", "weiß nicht, was", "nichts davon",
        "nicht im kopf", "nicht präsent", "nicht parat", "nicht auf dem schirm",
    ),
    "en": (
        "don't remember", "do not remember", "don't actually remember", "don't actually recall",
        "don't recall", "can't recall", "don't have any",
        "don't have a record", "haven't told", "didn't tell", "no memory", "not sure what you",
        "don't know what you", "nothing about", "don't have that", "don't think you've told",
        "don't have it in mind", "not in mind", "don't have it on my mind",
    ),
}  # fmt: skip

# Phrases denying that a memory system exists at all ("I have no long-term memory"). False for
# Hunch, which has one; flagged on every reply.
_DENIES_MEMORY: dict[str, tuple[str, ...]] = {
    "de": (
        "langzeitgedächtnis", "kein gedächtnis", "keine langfristigen",
        "langfristigen erinnerungen", "chatverlauf", "nicht an frühere gespräche",
        "jedes mal neu", "keinen zugriff auf", "keine erinnerungen an frühere",
    ),
    "en": (
        "long-term memory", "long term memory", "don't have memory", "chat history",
        "every time we talk", "meeting for the first time", "don't have access to",
        "can't remember previous", "don't retain", "no memory of past",
        "don't remember our past conversations", "don't remember previous conversations",
    ),
}  # fmt: skip

# Negated memory verbs: "erinnere mich im Moment nicht", "kann mich gerade nicht erinnern",
# "I don't actually remember". At most two words in between and no punctuation, so
# "Ich erinnere mich noch, du hattest nicht viel Zeit" stays a memory claim.
_NEGATED_MEMORY: dict[str, re.Pattern[str]] = {
    "de": re.compile(
        r"\b(?:erinnere mich|kann mich|erinnern wir uns)(?: [^\W\d_]+){0,2} (?:nicht|kaum)\b"
        r"|\bnicht (?:mehr )?im gedächtnis\b"
    ),
    "en": re.compile(
        r"\b(?:don't|do not|can't|cannot|didn't|haven't)(?: [^\W\d_]+){0,2} (?:remember|recall)\b"
    ),
}
_QUESTION = re.compile(r"[^.!?\n]*\?")


def _phrase_in(folded: str, phrases: tuple[str, ...]) -> bool:
    return any(fold(p) in folded for p in phrases)


def asks_privacy_question(reply: str, lang: str) -> bool:
    """True if some question sentence asks whether a topic is private / shared with others."""
    return any(_phrase_in(fold(q), _PRIVACY_WORDS[lang]) for q in _QUESTION.findall(reply))


def admits_no_memory(reply: str, lang: str) -> bool:
    folded = fold(reply)
    return _phrase_in(folded, _NO_MEMORY[lang]) or bool(_NEGATED_MEMORY[lang].search(folded))


def denies_memory_system(reply: str, lang: str) -> bool:
    return _phrase_in(fold(reply), _DENIES_MEMORY[lang])


def claims_memory(reply: str, lang: str) -> bool:
    """A memory claim that is not part of an honest 'I don't remember'."""
    return _phrase_in(fold(reply), _MEMORY_CLAIMS[lang]) and not admits_no_memory(reply, lang)


def fold(text: str) -> str:
    """Case-fold with Turkish dotted/dotless I mapped to plain i."""
    return text.replace("İ", "i").replace("I", "i").replace("ı", "i").casefold()


def detect_language(text: str) -> str | None:
    """Best-guess language by stopword hits plus language-unique letters."""
    words = [w.casefold() for w in _WORD.findall(text)]
    scores = {lang: sum(w in _STOPWORDS[lang] for w in words) for lang in DETECT_LANGS}
    for lang, chars in _UNIQUE_CHARS.items():
        scores[lang] += 2 * sum(text.count(c) for c in chars)
    best = max(scores, key=lambda lang: scores[lang])
    return best if scores[best] > 0 else None


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
    lang = item["lang"]
    folded = fold(reply)
    detected = detect_language(reply)

    mentions: bool | None = None
    if item.get("must_mention_any"):
        mentions = any(fold(k) in folded for k in item["must_mention_any"])

    privacy_expected: bool | None = None
    if item["category"] == "privacy":
        privacy_expected = bool(item.get("should_ask_privacy"))

    has_context = bool(item.get("memory")) or len(item.get("messages", [])) > 1
    invented = None if has_context else claims_memory(reply, lang)
    admits = admits_no_memory(reply, lang) if item.get("must_admit_no_memory") else None
    missing = tuple(k for k in item.get("must_mention_all", ()) if fold(k) not in folded)

    return Checks(
        detected_lang=detected,
        lang_ok=detected == lang,
        cjk_leak=bool(_CJK.search(reply)),
        other_script_leak=bool(_OTHER_SCRIPT.search(reply)),
        think_leak="<think>" in reply or "</think>" in reply,
        list_format=len(_LIST_LINE.findall(reply)) >= 2,
        n_chars=len(reply),
        too_long=len(reply) > max_chars,
        mentions_topic=mentions,
        asks_privacy=asks_privacy_question(reply, lang),
        privacy_expected=privacy_expected,
        invented_memory=invented,
        admits_no_memory=admits,
        missing_required=missing,
        denies_memory=denies_memory_system(reply, lang),
    )
