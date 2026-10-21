"""Rule-based reflection triggers in the user's message (Berk, Phase 4).

- asks_why: the user asks Hunch for the reason behind its own last reply ("Why did you say
  that?", "what makes you think so", "where's that coming from?"). Not: "why" about something
  else ("why is my cat so weird"), "why not", "that's why", the user's own reasons.
- accepts_offer: a short yes to "Just a hunch. Want me to think about it for a moment?".

Only used when the previous reply was hunch-chosen (asks_why) or an offer is open
(accepts_offer), so a false positive costs one turn's instruction, not a wrong memory.
"""

from __future__ import annotations

import re

from hunch.pipeline.checks import fold

_YOU = r"(?:you|u|ya)"
_WHY_PATTERNS = (
    # "why did you say that", "why would you think so", "why're you so careful", "why u say that"
    rf"\bwhy\s+(?:(?:do|did|does|would|are|were|is|have|had|'d|'re|re)\s+)?{_YOU}\b",
    # "why'd you", "whyd you" (blind set, Phase 4)
    rf"\bwhy'?d\s+{_YOU}\b",
    # "what led you to say that", "how did you come up with that" (blind set, Phase 4)
    rf"\bwhat\s+(?:led|leads|brought|brings)\s+{_YOU}\b",
    rf"\bhow\s+(?:did|do)\s+{_YOU}\s+come up with\b",
    # "what's behind that remark", "the thinking behind it" (blind set, Phase 4); "whats behind
    # that opinion" (blind set 2, Phase 5)
    r"\b(?:what's|whats|what is|thinking|reasoning|logic)\s+behind\s+(?:that|this|it|your)\b",
    # "how you got to that conclusion" (blind set 2, Phase 5)
    rf"\bhow\s+{_YOU}\s+(?:got|get|came|come|arrived)\s+(?:to|at)\s+(?:that|this)\b",
    # "why so cautious?", "why that?", "why this?"
    r"\bwhy\s+(?:so|that|this)\b(?!\s+(?:many|much|is|was|guy|girl|man|woman|thing|one)\b)",
    # "why?", "but why?", "hmm, why", "you seem hesitant, why?"
    r"(?:^|[,.!;:]\s*|\b(?:but|and|hmm+|huh|ok|okay|wait|so)\s+)why\s*[?!.]*$",
    # "how come you say that", "how come?"
    rf"\bhow come(?:\s+{_YOU}\b|\s*[?!.]*$)",
    # "what makes you say that", "what gave you that idea"; not "what makes you happy" (a question
    # about Hunch itself, blind sets 1 and 2)
    rf"\bwhat\s+(?:makes|made|gives|gave|is making)\s+{_YOU}\b"
    r"(?!\s+(?:happy|sad|smile|laugh|tick|excited|angry|upset|special|different|unique|"
    r"feel (?:good|better|happy|alive))\b)",
    # "where's that coming from", "where does this come from", "where did that come from"
    r"\bwhere(?:'s|\s+is|\s+does|\s+did|\s+do)?\s+(?:that|this|it)\s+(?:\w+\s+)?"
    r"(?:come|coming|came)\s+from\b",
    # "where'd you get the idea that..." (blind set 2, Phase 5)
    rf"\bwhere(?:'d|d|\s+are|\s+did)\s+{_YOU}\s+(?:get|getting|got)\s+(?:that|this|the idea)\b",
    # "what's that based on", "based on what?"
    r"\bwhat(?:'s|\s+is|\s+was)\s+(?:that|this|it)\s+based on\b|\bbased on what\b",
    # "what's your reasoning", "your reason for that"
    r"\b(?:your|ur)\s+reason(?:ing|s)?\b",
    rf"\bwhy\s+(?:do|did)\s+{_YOU}\s+feel\b",
)
_WHY = re.compile("|".join(f"(?:{p})" for p in _WHY_PATTERNS))
# "why not", "that's why", "I wonder why", "why do I / did I ..." are never about Hunch.
_NOT_WHY = re.compile(
    r"\bwhy not\b|\b(?:that's|that is|this is|which is|is)\s+why\b|\bwonder(?:ing)? why\b"
    r"|\bwhy\s+(?:do|did|am|was|should|can't|cannot|would|is)\s+i\b"
)

_YES = re.compile(
    r"^\W*(?:yes|yeah|yea|yep|yup|sure|ok|okay|please|go ahead|go on|do it|of course|"
    r"absolutely|definitely|please do|i'd like that|take your time|why not|i'd love that)\b"
)
_THINK = re.compile(r"\bthink (?:about it|it over|about that)\b")
_NO = re.compile(r"\b(?:no|nah|nope|don't|not now|never mind|nevermind)\b")
_MAX_YES_WORDS = 12


def asks_why(text: str) -> bool:
    folded = fold(text).strip()
    if not _WHY.search(folded):
        return False
    # "why not" etc. veto only when no other reason-asking pattern remains without them.
    return bool(_WHY.search(_NOT_WHY.sub(" ", folded)))


def accepts_offer(text: str) -> bool:
    folded = fold(text).strip()
    if len(folded.split()) > _MAX_YES_WORDS or _NO.search(folded):
        return False
    return bool(_YES.search(folded) or _THINK.search(folded))
