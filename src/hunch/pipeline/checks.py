"""Rule-based text checks shared by the turn pipeline and eval/ (Hunch speaks English only).

- Language: best guess by stopword hits plus language-unique letters; German, Turkish and French
  are detected only to catch input or replies in the wrong language. Foreign scripts (CJK,
  Cyrillic, Arabic, Hebrew, Thai) are flagged separately; Qwen sometimes drifts into Chinese.
- Memory talk: claims to remember something ("you told me"), honest admissions ("I don't have
  that in mind") and false descriptions of Hunch as having no memory ("no access to past chats").
"""

from __future__ import annotations

import re

REPLY_LANG = "en"  # the only language Hunch replies in
# Detected only to catch text in the wrong language; not languages Hunch speaks.
DETECT_LANGS = ("en", "de", "tr", "fr")

_STOPWORDS: dict[str, frozenset[str]] = {
    "en": frozenset(
        "the and you is it that to of i for what this your with so are be how have just it's "
        "that's do don't can my me was not but really if would about there".split()
    ),
    "de": frozenset(
        "und ich du das ist nicht die der den es mit ein eine einen auf aber wie was dir dich "
        "sehr auch schon noch mal für zu sich kann hast bist sind wir mein dein ganz echt oder "
        "wenn dass vielleicht gerade jetzt".split()
    ),
    "tr": frozenset(
        "ve bir bu çok ne de da mi mı mu mü için ama gibi sen ben nasıl var yok şey daha iyi "
        "sana seni senin değil ile kadar bence gerçekten biraz olur oldu şimdi belki hiç her "
        "neden çünkü sonra önce bana benim".split()
    ),
    "fr": frozenset(
        "je tu le la les et est pas un une des pour ce que qui vous moi ça avec mais très "
        "bonjour c'est suis".split()
    ),
}
_UNIQUE_CHARS = {"de": "äß", "tr": "ğışİ", "fr": "çèêàœ"}
_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?", re.UNICODE)
CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯豈-﫿]")
OTHER_SCRIPT = re.compile(r"[Ѐ-ӿ؀-ۿ֐-׿฀-๿]")

# Phrases claiming to remember something the user said before.
_MEMORY_CLAIMS = (
    "i remember", "you mentioned", "you told me", "last time", "you said earlier",
    "mentioning earlier", "as you said",
)  # fmt: skip

# Phrases admitting there is no such memory ("I don't have that in mind").
_NO_MEMORY = (
    "don't remember", "do not remember", "don't actually remember", "don't actually recall",
    "don't recall", "can't recall", "don't have any", "don't have a record", "haven't told",
    "didn't tell", "no memory", "not sure what you", "don't know what you", "nothing about",
    "don't have that", "don't think you've told", "don't have it in mind", "not in mind",
    "don't have it on my mind",
)  # fmt: skip
# Negated memory verbs ("I don't actually remember"); at most two words in between and no
# punctuation, so "Yes, I remember, you didn't like him" stays a memory claim.
_NEGATED_MEMORY = re.compile(
    r"\b(?:don't|do not|can't|cannot|didn't|haven't)(?: [^\W\d_]+){0,2} (?:remember|recall)\b"
)

# Phrases describing Hunch as having no memory system ("I have no long-term memory"). False
# for Hunch, which has one; flagged on every reply.
_DENIES_MEMORY = (
    "long-term memory", "long term memory", "don't have memory", "chat history",
    "every time we talk", "meeting for the first time", "don't have access to",
    "can't remember previous", "don't retain", "no memory of past",
    "don't remember our past conversations", "don't remember previous conversations",
)  # fmt: skip


# A negated memory, record or access whose object is the past conversations themselves ("I don't
# have a memory of our past conversations", "no access to earlier chats"): describes Hunch as not
# keeping its conversations. Found in the Phase 3 bench; the phrase list above missed it.
# Topic-scoped admissions stay allowed (Phase 1): "...no memories of our past conversations about
# your job interview right now" is about one topic, not the memory system.
_DENIES_PAST_CONVERSATIONS = re.compile(
    r"\b(?:don't|do not|can't|cannot|haven't|no)\b[^.!?\n]{0,30}"
    r"\b(?:memory|memories|record|records|access|recollection)\s+(?:of|to|from)\s+"
    r"(?:(?:our|any|the|my)\s+)?(?:past|previous|earlier|prior|old)\s+"
    r"(?:conversations?|chats?|talks?|sessions?)\b"
    r"(?!\s+(?:about|regarding|concerning|on)\b)"
)


def fold(text: str) -> str:
    return text.casefold().replace("’", "'")


def phrase_in(folded: str, phrases: tuple[str, ...]) -> bool:
    return any(p in folded for p in phrases)


def admits_no_memory(text: str) -> bool:
    folded = fold(text)
    return phrase_in(folded, _NO_MEMORY) or bool(_NEGATED_MEMORY.search(folded))


def denies_memory_system(text: str) -> bool:
    folded = fold(text)
    return phrase_in(folded, _DENIES_MEMORY) or bool(_DENIES_PAST_CONVERSATIONS.search(folded))


def claims_memory(text: str) -> bool:
    """A memory claim that is not part of an honest 'I don't remember'."""
    return phrase_in(fold(text), _MEMORY_CLAIMS) and not admits_no_memory(text)


def memory_claim_sentences(text: str) -> list[str]:
    """The sentences of `text` that claim a memory, unless the text admits having none."""
    if admits_no_memory(text):
        return []
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [s for s in sentences if phrase_in(fold(s), _MEMORY_CLAIMS)]


def detect_language(text: str) -> str | None:
    """Best-guess language by stopword hits plus language-unique letters."""
    words = [w.casefold() for w in _WORD.findall(text)]
    scores = {lang: sum(w in _STOPWORDS[lang] for w in words) for lang in DETECT_LANGS}
    for lang, chars in _UNIQUE_CHARS.items():
        scores[lang] += 2 * sum(text.count(c) for c in chars)
    best = max(scores, key=lambda lang: scores[lang])
    return best if scores[best] > 0 else None


def foreign_script(text: str) -> bool:
    return bool(CJK.search(text) or OTHER_SCRIPT.search(text))


def is_english_input(text: str) -> bool:
    """The "is the input English?" check. Short or unclear input ("ok", "Anna!") gets the
    benefit of the doubt; a foreign script or a clear German/Turkish/French guess does not."""
    if foreign_script(text):
        return False
    return detect_language(text) in (REPLY_LANG, None)
