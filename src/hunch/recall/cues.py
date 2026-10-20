"""Cue extraction with the LLM and validated JSON output (design.md, "Tetikleyiciler").

The model returns {"cues": [{"type", "value", "strength"}]}; the reply is parsed strictly, every
cue is validated and normalised to the store's "type:value" form, and anything invalid is dropped
and reported. One retry on unparseable output, then an empty result (never a crash): missing
cues only weaken recall, they never break a turn.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from hunch.memory.schema import CUE_TYPES
from hunch.recall.dates import find_date_expressions, resolve_date

# Fixed vocabulary so the same feeling always becomes the same cue (and fan counts work).
EMOTIONS: tuple[str, ...] = (
    "joy", "love", "gratitude", "pride", "excitement", "calm", "sad", "lonely", "grief", "anger",
    "annoyed", "fear", "anxious", "worry", "stress", "tired", "shame", "guilt", "disappointment",
    "surprise", "nostalgia",
)  # fmt: skip
MAX_EMOTIONS = 2
MAX_PHRASES = 1
# A "person" made only of these words is a role, not a name ("my mum", "little brother").
_ROLE_WORDS = frozenset(
    [
        "mum",
        "mom",
        "mother",
        "mommy",
        "mummy",
        "dad",
        "father",
        "daddy",
        "grandpa",
        "grandma",
        "grandmother",
        "grandfather",
        "granny",
        "nan",
        "nana",
        "gran",
        "brother",
        "sister",
        "bro",
        "sis",
        "aunt",
        "auntie",
        "uncle",
        "cousin",
        "niece",
        "nephew",
        "son",
        "daughter",
        "kid",
        "kids",
        "baby",
        "wife",
        "husband",
        "partner",
        "girlfriend",
        "boyfriend",
        "fiance",
        "fiancee",
        "boss",
        "manager",
        "doctor",
        "dentist",
        "therapist",
        "teacher",
        "landlord",
        "landlady",
        "neighbour",
        "neighbor",
        "coworker",
        "colleague",
        "friend",
        "friends",
        "roommate",
        "flatmate",
        "my",
        "little",
        "big",
        "older",
        "younger",
        "old",
        "new",
        "best",
        "the",
    ]
)

Generate = Callable[[list[dict[str, str]]], str]

SYSTEM_PROMPT = """You extract memory cues from one chat message a user sent. Reply with JSON only, no other text:
{{"cues": [{{"type": "<type>", "value": "<value>", "strength": <0.0-1.0>}}]}}

Types:
- person: people the user knows, named in the message (first names or nicknames as used). Not pronouns, not roles like "my mum", "my dad", "my boss", "my little brother". Not celebrities, artists, singers or fictional characters.
- place: named places (cities, countries, named venues, parks, lakes). Not generic places like "home" or "the office".
- song: song titles. Artist names are not songs.
- film: film or TV series titles.
- date: a specific day the user mentions, written exactly as the user said it ("tomorrow", "Friday", "last Sunday", "March 3rd", "in two days", "Christmas"); do not calculate it. Vague times like "soon", "last night", "this weekend", "next spring" or "last year" are not dates.
- emotion: the user's own feelings in this message, at most 2, only from: {emotions}. Include feelings that are clearly implied, not only named ones: relief -> calm, being alone again -> lonely, thanking you -> gratitude, missing old times -> nostalgia, someone dying -> grief, dreading something -> anxious, can't wait -> excitement, not sleeping -> tired. Most personal messages carry at least one; a plain question or small talk carries none.
- phrase: at most 1 distinctive personal expression or nickname the user uses for something (e.g. "the blue house"). Usually none.

Values: lowercase, words joined with underscores, punctuation and apostrophes removed, articles kept when they are part of a title ("the_martian").
Today is {today} ({weekday}).
Strength: how central the cue is to the message, 1.0 = what the message is about, 0.3 = mentioned in passing.
If there are no cues, reply {{"cues": []}}."""


@dataclass(frozen=True, slots=True)
class CueExtraction:
    cues: dict[str, float]  # "type:value" -> strength
    dropped: tuple[str, ...] = ()  # reasons for every rejected item
    raw: str = ""
    attempts: int = 1
    errors: tuple[str, ...] = field(default_factory=tuple)
    # "date:<resolved>" cues the rule-based finder produced (whether or not the LLM had them too)
    rule_dates: tuple[str, ...] = ()


def normalize_value(value: str) -> str:
    """lowercase, accents stripped ("Amélie" -> "amelie"), words joined with underscores."""
    v = unicodedata.normalize("NFKD", value)
    v = "".join(ch for ch in v if not unicodedata.combining(ch))
    v = v.casefold().replace("’", "").replace("'", "")
    v = re.sub(r"[^\w\s-]", " ", v)
    return re.sub(r"[\s_]+", "_", v).strip("_")


def _parse_json(text: str) -> dict:
    """The first JSON object in the reply (models sometimes wrap it in a code fence)."""
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in reply")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict) or not isinstance(data.get("cues"), list):
        raise ValueError("reply must be an object with a 'cues' list")
    return data


def validate_cues(items: list, today: date) -> tuple[dict[str, float], list[str]]:
    cues: dict[str, float] = {}
    dropped: list[str] = []
    per_type: dict[str, int] = {}
    for item in items:
        if not isinstance(item, dict):
            dropped.append(f"not an object: {item!r}")
            continue
        kind, value, strength = item.get("type"), item.get("value"), item.get("strength", 0.5)
        if kind not in CUE_TYPES:
            dropped.append(f"unknown type: {kind!r}")
            continue
        if not isinstance(value, str) or not (norm := normalize_value(value)):
            dropped.append(f"empty value for {kind}")
            continue
        if kind == "emotion" and norm not in EMOTIONS:
            dropped.append(f"emotion not in vocabulary: {norm!r}")
            continue
        if kind == "person" and all(
            w in _ROLE_WORDS or w.removesuffix("s") in _ROLE_WORDS for w in norm.split("_")
        ):
            dropped.append(f"role, not a name: {norm!r}")
            continue
        if kind == "date":
            resolved = resolve_date(value, today)
            if resolved is None:
                dropped.append(f"vague or unresolvable date: {value!r}")
                continue
            norm = resolved
        limit = {"emotion": MAX_EMOTIONS, "phrase": MAX_PHRASES}.get(kind)
        if limit is not None and per_type.get(kind, 0) >= limit:
            dropped.append(f"too many {kind} cues: {norm!r}")
            continue
        try:
            s = float(strength)
        except (TypeError, ValueError):
            s = 0.5
        key = f"{kind}:{norm}"
        per_type[kind] = per_type.get(kind, 0) + (key not in cues)
        cues[key] = max(cues.get(key, 0.0), min(max(s, 0.0), 1.0))
    return cues, dropped


def build_messages(text: str, today: date) -> list[dict[str, str]]:
    system = SYSTEM_PROMPT.format(
        today=today.isoformat(), weekday=today.strftime("%A"), emotions=", ".join(EMOTIONS)
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": text}]


def merge_rule_dates(text: str, today: date, cues: dict[str, float]) -> tuple[str, ...]:
    """Add the date cues the rule-based finder sees in `text` to `cues` (in place).

    The LLM misses many dates; a found date it also has keeps the higher strength, a new one gets
    the same default strength as a cue without one.
    """
    keys: list[str] = []
    for expr in find_date_expressions(text):
        resolved = resolve_date(expr, today)
        if resolved is None:
            continue
        key = f"date:{resolved}"
        cues[key] = max(cues.get(key, 0.0), 0.5)
        if key not in keys:
            keys.append(key)
    return tuple(keys)


def extract_cues(
    text: str, today: date, generate: Generate, retries: int = 1, *, rule_dates: bool = True
) -> CueExtraction:
    """LLM cues plus, unless `rule_dates` is False, the dates the rule-based finder sees."""
    messages = build_messages(text, today)
    errors: list[str] = []
    raw = ""
    cues: dict[str, float] = {}
    dropped: list[str] = []
    attempts = retries + 1
    for attempt in range(1, retries + 2):
        raw = generate(messages)
        try:
            data = _parse_json(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            errors.append(f"attempt {attempt}: {exc}")
            continue
        cues, dropped = validate_cues(data["cues"], today)
        attempts = attempt
        break
    found = merge_rule_dates(text, today, cues) if rule_dates else ()
    return CueExtraction(cues, tuple(dropped), raw, attempts, tuple(errors), found)


def llm_generate(model: object, max_new_tokens: int = 256) -> Generate:
    """Adapter for hunch.llm.model.ChatModel: greedy, no thinking, short output."""
    from hunch.llm.model import SamplingSettings

    sampling = SamplingSettings(max_new_tokens=max_new_tokens, do_sample=False)

    def generate(messages: list[dict[str, str]]) -> str:
        return model.generate(messages, sampling).text  # type: ignore[attr-defined]

    return generate
