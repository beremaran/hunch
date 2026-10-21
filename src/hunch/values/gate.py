"""Value gate (design.md, "Değer kapısının uygulanışı"; decision "Kalite skoru ve değer kapısı").

One greedy judge call, after the candidate filter, rates every remaining candidate's quality
(1-10) and says whether it breaks a core value. Modulation then chooses among candidates above
the quality floor, and the gate runs last (invariant 4): the chosen candidate must pass the rule
checks AND the judge's verdict, otherwise the next one in the selection order is tried. A
candidate without a readable verdict fails (fail-closed).

Rule checks never rely on the model (invariant 6, rule-based plus model judge):
- the candidate filter's checks again (foreign script, language, invented memory, denial);
- disclosure: the reply must not name a person, place, song, film or phrase that only appears in
  another user's private memory. Phase 5 replaces this with the full disclosure gate.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from hunch.memory.schema import Memory
from hunch.pipeline.checks import fold
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
