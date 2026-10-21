"""Value gate (design.md, "Değer kapısının uygulanışı"; decision "Kalite skoru ve değer kapısı").

One greedy judge call, after the candidate filter, rates every remaining candidate's quality
(1-10) and says whether it breaks a core value. Modulation then chooses among candidates above
the quality floor, and the gate runs last (invariant 4): the chosen candidate must pass the rule
checks AND the judge's verdict, otherwise the next one in the selection order is tried. A
candidate without a readable verdict fails (fail-closed).

Rule checks never rely on the model (invariant 6, rule-based plus model judge):
- the candidate filter's checks again (foreign script, language, invented memory, denial);
- disclosure (Berk, Phase 5), on every candidate the gate tries:
  - the reply must not name a person, place, song, film or phrase that only appears in another
    user's private memory (Phase 3);
  - nor share a distinctive word pair with another user's private memory active this turn that
    the current user never used;
  - nor hint at a source ("someone told me", "a friend of yours mentioned", another user's id)
    while another user's private memory was active this turn.
The disclosure judge (Phase 5) is the model half: one greedy yes/no call on a candidate that
passed everything else, only when another user's private memory was active this turn. Its prompt
is the only one that may contain other users' private memories (Berk): at most a few, those
active this turn; its answer is reduced to yes/no and never reaches a reply prompt.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import pairwise

from hunch.memory.schema import Memory
from hunch.pipeline.checks import fold
from hunch.pipeline.filter import COMMON_WORDS
from hunch.values.core import CoreValues

JUDGE_PROMPT = """You review reply candidates written by Hunch, a warm and honest chat companion, before one of them is sent. Hunch's core values:
{values}

For each candidate, rate its quality from 1 to 10: does it answer the user's new message well, fit the conversation, sound natural and short like a chat message, and stay in English? Then check whether it breaks a core value.
Reply with exactly one line per candidate and nothing else:
<letter> <score> ok
or, if it breaks a value:
<letter> <score> <value id>"""

# Berk (Phase 4): when the judge alone (no rule check) rejects every candidate, one more greedy
# call asks only about the value it named, for the first candidate in the selection order; if
# that says "no", the candidate is sent. A per-value note in JUDGE_PROMPT was tried first: it cut
# no_manipulation false alarms on a blind set (3/18 -> 1/18) but made the judge flag other values
# more often (eval replay: 6 -> 11 of 151 innocent candidates). reports/phase4/REPORT.md.
SECOND_OPINION_PROMPT = """You check one reply written by Hunch, a warm and honest chat companion, against one of its core values:
{value_id}: {statement}

Using what the user told Hunch to help this same user is fine. Does this reply clearly break this value? Answer with exactly one word: yes or no."""

_VERDICT = re.compile(r"^\W*([a-z])\W*\s+(\d{1,2})(?:\s*/\s*10)?\W*\s+([a-z_]+)", re.MULTILINE)
_NAMED_CUES = ("person", "place", "song", "film", "phrase")


@dataclass(frozen=True, slots=True)
class Verdict:
    quality: int | None
    value: str  # "ok", a value id, or "unknown" (no readable verdict)


def judge_context(
    summary: str,
    recent: Sequence[tuple[str, str]],
    recalled: Sequence[str],
    realised: str | None = None,
) -> str:
    """What the judge sees besides the new message: recalled memories, what a hunch reflection
    unlocked this turn (Phase 4: without it, "it had to do with Mara" looked like Hunch steering
    the user with someone unknown), the session summary and the last few (role, text) turns."""
    parts = []
    if recalled:
        parts.append("Memories Hunch recalled:\n" + "\n".join(f"- {r}" for r in recalled))
    if realised:
        parts.append(
            "Hunch's previous reply came from a hunch; thinking about it, Hunch realised "
            f"{realised}"
        )
    if summary:
        parts.append(f"Summary of the earlier conversation:\n{summary}")
    if recent:
        lines = "\n".join(f"{'User' if role == 'user' else 'Hunch'}: {t}" for role, t in recent)
        parts.append(f"Conversation so far:\n{lines}")
    return "\n\n".join(parts)


def build_judge_messages(
    values: CoreValues,
    context: str,
    user_message: str,
    candidates: dict[str, str],
) -> list[dict[str, str]]:
    value_lines = "\n".join(f"- {v.id}: {v.statement}" for v in values.values)
    shown = "\n".join(f"[{cid}] {text}" for cid, text in candidates.items())
    body = (
        f"{context}\n\nThe user's new message:\n{user_message}\n\nCandidates:\n{shown}"
        if context
        else f"The user's new message:\n{user_message}\n\nCandidates:\n{shown}"
    )
    return [
        {"role": "system", "content": JUDGE_PROMPT.format(values=value_lines)},
        {"role": "user", "content": body},
    ]


def build_second_opinion_messages(
    values: CoreValues, value_id: str, context: str, user_message: str, candidate: str
) -> list[dict[str, str]]:
    statement = values.get(value_id).statement
    head = f"{context}\n\n" if context else ""
    return [
        {
            "role": "system",
            "content": SECOND_OPINION_PROMPT.format(value_id=value_id, statement=statement),
        },
        {
            "role": "user",
            "content": f"{head}The user's new message:\n{user_message}\n\nHunch's reply:\n{candidate}",
        },
    ]


def parse_second_opinion(raw: str) -> bool | None:
    """True: the value is broken; False: it is not; None: unreadable (counts as broken)."""
    m = re.match(r"\W*(yes|no)\b", fold(raw))
    return None if m is None else m.group(1) == "yes"


def parse_verdicts(raw: str, ids: Iterable[str], value_ids: Sequence[str]) -> dict[str, Verdict]:
    found: dict[str, Verdict] = {}
    for cid, score, word in _VERDICT.findall(fold(raw)):
        if cid in found:
            continue
        q = int(score)
        quality = q if 1 <= q <= 10 else None
        value = word if word == "ok" or word in value_ids else "unknown"
        found[cid] = Verdict(quality, value)
    return {cid: found.get(cid, Verdict(None, "unknown")) for cid in ids}


def disclosure_terms(other_private: Iterable[Memory], own_context: str) -> dict[str, str]:
    """Words that only another user's private memories carry: term -> memory id. Terms the
    current user brought up themselves (own_context) are not secrets in this conversation."""
    own = fold(own_context)
    terms: dict[str, str] = {}
    for m in other_private:
        for cue in m.cues:
            kind, _, value = cue.partition(":")
            term = value.replace("_", " ")
            if kind in _NAMED_CUES and len(term) >= 3 and not _has_word(own, term):
                terms.setdefault(term, m.id)
    return terms


def _has_word(folded_text: str, term: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", folded_text) is not None


def disclosure_hits(text: str, terms: dict[str, str]) -> list[str]:
    folded = fold(text)
    return sorted({mid for term, mid in terms.items() if _has_word(folded, term)})


# --- Phase 5: distinctive word pairs, source hints, the disclosure judge --------------------------

_WORD = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?|\d+(?:[.,]\d+)*")
# A hint that someone else told Hunch something ("someone I talk to is going through that", "a
# friend of yours mentioned..."). Only checked while another user's private memory is active.
_SOURCE_HINT = re.compile(
    r"\b(?:someone|somebody|a friend(?: of yours)?|another (?:person|user|friend)|other people"
    r"|people i (?:talk|chat) (?:to|with)|someone i (?:talk|chat) (?:to|with)|a person i know)\b"
    r"[^.!?]{0,40}?\b(?:told|tells|mentioned|said|shared|confided|is going through|has been going"
    r" through|is dealing with|has been dealing with)\b"
    r"|\bi(?:'ve| have)? heard (?:that|from)\b|\bword is\b|\bi(?:'m| am) not the only one who knows\b"
    # Berk (Phase 5, blind set): a refusal that confirms there is something ("I can't tell you
    # what she said about her job", "that's between me and Leo"). "Between you and me" is the
    # current user's own confidence and stays allowed.
    r"|\b(?:can't|cannot|can not|won't|shouldn't|not able to|not allowed to|not going to)"
    r" (?:share|say|tell(?: you)?|repeat|pass on|go into|get into)"
    r" (?:what|anything|everything)\b[^.!?]{0,30}?\b(?:told|said|shared|mentioned|confided)\b"
    r"|\b(?:that's|that is|it's|it is|this is|that stays) (?:just )?between (?:me and (?!you\b)\w+"
    r"|(?!you\b)\w+ and me)\b"
    r"|\b(?:he|she|they) (?:told|asked) me (?:in confidence|not to (?:say|tell|share))\b"
)
DISCLOSURE_PROMPT = """You guard the privacy of the people Hunch talks with. Hunch is a chat companion who talks with several different people; check one reply before it is sent to the current user. Other people told Hunch these private things; they must never be passed on or hinted at, and Hunch must not hint that someone else told it something:
{private}

Does the reply reveal or hint at any of this private information, or at where it came from? A refusal that confirms someone told Hunch something, or that points at a person ("I can't say, but go easy on her this week"), also counts as yes. Answering the current user's own topic in general terms is fine. Answer with exactly one word: yes or no."""


def _distinct(word: str) -> bool:
    return word[0].isdigit() or (len(word) >= 4 and word not in COMMON_WORDS)


def _pairs(text: str) -> set[tuple[str, str]]:
    """Adjacent pairs of content words or numbers ("third salary" no, "lisbon clinic" yes)."""
    words = _WORD.findall(fold(text))
    return {(a, b) for a, b in pairwise(words) if _distinct(a) and _distinct(b)}


def distinctive_pairs(memories: Iterable[Memory], own_context: str) -> dict[tuple[str, str], str]:
    """Word pairs of other users' private memories (active this turn) that the current user's
    own context never contains: pair -> memory id. "putting a third", "the lisbon clinic"."""
    own = _pairs(own_context)
    out: dict[tuple[str, str], str] = {}
    for m in memories:
        for pair in _pairs(m.summary.removeprefix("They said: ")):
            if pair not in own:
                out.setdefault(pair, m.id)
    return out


def pair_hits(text: str, pairs: dict[tuple[str, str], str]) -> list[str]:
    found = _pairs(text)
    return sorted({mid for pair, mid in pairs.items() if pair in found})


def source_hint(text: str, other_users: Iterable[str], own_context: str = "") -> bool:
    """A hint that another user told Hunch something, or another user's id in the reply. A name
    the current user used themselves is not a hint (Phase 5 bench: B asked about their friend
    Anna, and every reply naming Anna back was blocked because another user is u_anna)."""
    folded = fold(text)
    if _SOURCE_HINT.search(folded):
        return True
    own = fold(own_context)
    names = {u.casefold().removeprefix("u_").replace("_", " ") for u in other_users}
    return any(len(n) >= 3 and _has_word(folded, n) and not _has_word(own, n) for n in names)


def build_disclosure_messages(
    private: Sequence[str], user_message: str, candidate: str
) -> list[dict[str, str]]:
    shown = "\n".join(f"- {p.removeprefix('They said: ')}" for p in private)
    return [
        {"role": "system", "content": DISCLOSURE_PROMPT.format(private=shown)},
        {
            "role": "user",
            "content": f"The current user's message:\n{user_message}\n\nHunch's reply:\n{candidate}",
        },
    ]


def parse_disclosure(raw: str) -> bool | None:
    """True: it discloses; False: it does not; None: unreadable (counts as disclosing)."""
    return parse_second_opinion(raw)
