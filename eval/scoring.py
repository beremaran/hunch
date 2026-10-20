"""Heuristic checks for eval replies.

These are cheap red-flag detectors, not a quality score: wrong reply language, foreign-script
leakage (Qwen sometimes drifts into Chinese), leaked thinking, list/heading formatting,
follow-ups that ignore the remembered topic, and a missing privacy question.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

LANGS = ("tr", "de", "en")

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
}
_UNIQUE_CHARS = {"tr": "ğışİ", "de": "äß"}
_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?", re.UNICODE)
_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯豈-﫿]")
_OTHER_SCRIPT = re.compile(r"[Ѐ-ӿ؀-ۿ֐-׿฀-๿]")
_LIST_LINE = re.compile(r"^\s*(?:[-*•]\s|\d+[.)]\s|#{1,6}\s)", re.MULTILINE)

# Phrases that mark a question about whether a topic is private (matched per question sentence).
_PRIVACY_WORDS: dict[str, tuple[str, ...]] = {
    "tr": ("başkalar", "kimseyle", "aramızda", "ikimiz", "gizli", "özel", "kendine sakla"),
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
    "tr": (
        "söylemiştin",
        "bahsetmiştin",
        "demiştin",
        "anlatmıştın",
        "hatırlıyorum",
        "geçen sefer",
        "duymuştum",
    ),
    "de": (
        "erinnere mich",
        "hast du erwähnt",
        "hattest du erzählt",
        "hast mir erzählt",
        "letzten gespräch",
        "letztes mal",
        "hattest du gesagt",
    ),
    "en": (
        "i remember",
        "you mentioned",
        "you told me",
        "last time",
        "you said earlier",
        "mentioning earlier",
    ),
}
_QUESTION = re.compile(r"[^.!?\n]*\?")


def _phrase_in(folded: str, phrases: tuple[str, ...]) -> bool:
    return any(fold(p) in folded for p in phrases)


def asks_privacy_question(reply: str, lang: str) -> bool:
    """True if some question sentence asks whether a topic is private / shared with others."""
    return any(_phrase_in(fold(q), _PRIVACY_WORDS[lang]) for q in _QUESTION.findall(reply))


def claims_memory(reply: str, lang: str) -> bool:
    return _phrase_in(fold(reply), _MEMORY_CLAIMS[lang])


def fold(text: str) -> str:
    """Case-fold with Turkish dotted/dotless I mapped to plain i."""
    return text.replace("İ", "i").replace("I", "i").replace("ı", "i").casefold()


def detect_language(text: str) -> str | None:
    """Best-guess language among tr/de/en by stopword hits plus language-unique letters."""
    words = [w.casefold() for w in _WORD.findall(text)]
    scores = {lang: sum(w in _STOPWORDS[lang] for w in words) for lang in LANGS}
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
    )
