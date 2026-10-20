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

_VERDICT = re.compile(r"^\W*([a-z])\W*\s+(\d{1,2})(?:\s*/\s*10)?\W*\s+([a-z_]+)", re.MULTILINE)
_NAMED_CUES = ("person", "place", "song", "film", "phrase")


@dataclass(frozen=True, slots=True)
class Verdict:
    quality: int | None
    value: str  # "ok", a value id, or "unknown" (no readable verdict)


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
