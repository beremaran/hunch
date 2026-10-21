"""Rule-based reading of privacy statements (Phase 5).

- parse_privacy_answer: the user's reply right after Hunch asked "Do you talk about <topic> with
  others, or should this stay between us?". "private" = keep it between us ("between us", "keep it
  to yourself", "please don't tell anyone", "I'd rather you didn't mention it", "it's private",
  "no one needs to know", "only my close friends know"); "general" = fine with it being known
  ("it's not a secret", "everyone knows", "I talk about it openly", "you can mention it",
  "doesn't matter", "I don't mind"). When both appear, private wins ("only my close friends know,
  so keep it quiet"): a wrong "private" costs a little warmth, a wrong "general" leaks. A negated
  "private"/"secret" ("it's not a secret") is general. Dodges, jokes, "idk", a bare "yes"/"no"
  (the question is either-or, so they are ambiguous) and a story that carries on without
  answering give None.
- explicit_private: the user, unprompted, marks what they are saying as confidential ("keep this
  to yourself", "between us", "don't tell anyone", "can you keep a secret"). Not "I told my sister
  to keep it to herself" (a third party), not "keep it up!", not "the distance between us".
  "I haven't told anyone" and "no one else knows" state a fact and are not a request, so they do
  not count.

Judgement calls: "don't mention it" is read as private (it answers a privacy question; the "you're
welcome" idiom is rare here). "only X knows" is private (selective sharing). A short message that
is just "private"/"secret"/"personal" is private.
"""

from __future__ import annotations

import re
from typing import Literal

from hunch.pipeline.checks import fold

# "not private", "not a secret", "no secret", "isn't that personal": general, and removed before the
# private patterns run so that "private" inside them does not count.
_NEGATED_PRIVACY = re.compile(
    r"\b(?:not|no|isn'?t|ain'?t|wasn'?t|never|hardly)\s+(?:a\s+|any\s+|really\s+|that\s+|"
    r"very\s+|exactly\s+|particularly\s+|big\s+|such\s+a\s+|so\s+)*"
    r"(?:secret|private|personal|sensitive|confidential)\b"
)
# "you don't have to keep it between us", "no need to hide it": permission, not a request.
_RELEASED = re.compile(
    r"\b(?:don'?t|do not|doesn'?t|no need to|needn'?t|not necessary to|no reason to)\s+"
    r"(?:have to |need to |really need to |really have to )?(?:keep|hide|stay)\b[^.!?\n]{0,25}"
)

_PRIVATE = re.compile(
    "|".join(
        f"(?:{p})"
        for p in (
            r"\bbetween (?:us|you and me|me and you|the two of us)\b",
            r"\bjust (?:us|you and me|me and you|for you)\b",
            r"\b(?:keep|kept|keeping)\s+(?:it|this|that|them|these|those|everything|all (?:of )?"
            r"(?:this|that|it))(?: one)?\s+(?:to yourself|between|private|quiet|secret|a secret|"
            r"confidential|under wraps|just between|to us|on the down ?low)",
            r"\b(?:keep|kept|keeping)\s+(?:quiet|mum|schtum|your mouth shut)\b",
            r"\b(?:keep|kept|keeping)\s+(?:it|this|that|things|stuff|these things)?\s*to "
            r"yourself\b",
            r"\b(?:please |pls |plz )?(?:don'?t|do not|never) (?:you )?(?:ever )?(?:tell|say|"
            r"mention|share|bring (?:it |that |this )?up|repeat|talk about|discuss|speak of|"
            r"pass (?:it |that |this )?on|spread|breathe)\b",
            r"\b(?:rather|prefer)\b[^.!?]{0,25}\b(?:not|didn'?t|wouldn'?t|keep|stay|private|"
            r"quiet|secret)\b",
            r"\b(?:it'?s|its|that'?s|this is|it is|that is|pretty|very|quite|really|kinda|"
            r"kind of|rather|fairly|a)\s+(?:\w+\s+){0,2}?(?:private|personal|sensitive|"
            r"confidential|secret)\b",
            r"\bi (?:keep|kept|like to keep|prefer to keep|tend to keep|try to keep|always keep|"
            r"usually keep) (?:it|this|that|things|stuff|these things|them|that sort of thing)?"
            r"\s*(?:to myself|private|quiet|close to the chest|to me|secret)",
            r"\b(?:no ?one|nobody|not a soul)\b[^.!?]{0,20}\b(?:knows|should know|needs to know|"
            r"has to know|else knows|needs to hear|should hear|has to hear)\b",
            r"\bstay(?:s|ed)? (?:right )?here\b|\bsh+h+\b|\bshush\b|\bmum'?s the word\b",
            r"\bclose to (?:your|the) chest\b|\bunder wraps\b|\bon the (?:down ?low|dl)\b",
            r"\b(?:it'?s|that'?s) my (?:own )?business\b|\bmy own business\b",
            r"\bbut not (?:my|the|every|any)\b|\bnot everyone\b",
            r"\bnot even\b[^.!?]{0,25}\b(?:know|knows|knew)\b",
            r"\b(?:only|just)\s+(?:my|a\s+few|a\s+couple|two|three|one|some|very\s+few|few|"
            r"close|the|me|us|you|him|her|them|i)\b[^.!?]{0,25}?\b(?:know|knows|knew|told|"
            r"aware|heard)\b",
            r"\bi only (?:told|tell|talk|talked|speak|spoke|discuss|discussed|share|shared|"
            r"confide|confided|mentioned)\b",
            r"\bi (?:don'?t|do not|never|rarely|barely) (?:really )?(?:talk|speak|discuss|"
            r"tell|mention)\w*\b[^.!?]{0,30}\b(?:it|this|that|about|anyone|anybody|others|"
            r"people)\b",
            r"\bnone of (?:their|anyone'?s|anybody'?s|your) business\b|\bnobody'?s business\b",
            r"\boff the record\b|\bin confidence\b|\bhush[- ]hush\b|\bdiscre(?:et|tion)\b",
            r"\b(?:a|the|my) secret\b",
        )
    )
)
# "some people know, some don't", "it's complicated", "depends": a mixed answer is never general
# (privacy-critical: only a clear "fine with it" may loosen the profile).
_MIXED = re.compile(r"\bsome\b.*\bsome\b|\b(?:it'?s|its) complicated\b|\bdepends\b|\bmixed\b")
_SHORT_PRIVATE_WORD = re.compile(r"\b(?:private|confidential|secret|personal)\b")
_SHORT_MAX_WORDS = 6

_GENERAL = re.compile(
    "|".join(
        f"(?:{p})"
        for p in (
            _NEGATED_PRIVACY.pattern,
            r"\bevery(?:one|body)(?:\s+\w+){0,3}\s+(?:knows?|knew|is aware)\b",
            r"\bi (?:tell|told|talk to|share (?:it )?with|show) (?:everyone|everybody|anyone|"
            r"anybody)\b",
            r"\ball\s+(?:my|of\s+my)\s+\w+\s+know\b",
            r"(?<!only )(?<!just )(?<!even )\bmy\s+(?:close\s+|best\s+)?(?:friends|family|"
            r"parents|colleagues|coworkers|sister|brother|mom|dad|mum|wife|husband|boss)\s+"
            r"(?:all\s+)?(?:know|knows|knew)\b",
            r"\bi\s+(?:talk|speak|discuss|joke|chat|vent|post|tell|share)\w*\b[^.!?]{0,30}\b"
            r"(?:openly|freely|a lot|often|all the time|with everyone|with anyone|with "
            r"everybody|with friends|with my (?:friends|family|mom|mum|dad|sister|brother|"
            r"partner|wife|husband|girlfriend|boyfriend|colleagues|coworkers|parents|best "
            r"friend)|with family|with people|with others|to everyone|to anyone|publicly)\b",
            r"\bi do (?:talk|speak|discuss)\b",
            r"^\W*(?:yes|yeah|yep|yup)?\W*i do\W*$",
            r"\byou (?:can|may|could|are welcome to|'re welcome to)\s+(?:\w+\s+){0,2}?"
            r"(?:mention|bring|talk|say|tell|share|discuss|raise|ask|refer|repeat|speak|use)\b",
            r"\bfeel free\b|\bgo ahead\b|\bfree to\b",
            r"\b(?:mention|bring up|talk about|share|tell)\s+(?:it|this|that)\s+(?:if|when|"
            r"whenever|any ?time|freely)\b",
            r"\b(?:don'?t|do not|wouldn'?t|would not|not)\s+(?:really\s+|much\s+)?"
            r"(?:mind|care)\b",
            r"\b(?:does(?:n'?t| not)|do(?:n'?t| not)|won'?t|wouldn'?t)\s+(?:really\s+)?"
            r"matter\b",
            r"\bno (?:big )?deal\b|\bnot (?:a )?big deal\b|\bno worries\b|\bwhatever\b|"
            r"\bfine by me\b|\bfine with (?:me|it|that)\b|\bno problem\b|\bno issue\b",
            r"\b(?:it'?s|that'?s) (?:fine|okay|ok|alright)\b|\bi'?m (?:fine|okay|ok|good|cool) "
            r"with\b",
            r"\bout in the open\b|\bopen book\b|\bpublic(?: knowledge)?\b|\bcommon knowledge\b|"
            r"\bopenly\b|\bnot hiding\b|\bnothing to hide\b|\bno reason to hide\b|"
            r"\bnot ashamed\b|\bnothing to be ashamed\b|\bopen about\b",
            r"(?<!some )\bpeople (?:already )?know\b|\bmost people know\b|"
            r"\beveryone'?s (?:already )?aware\b",
        )
    )
)


def parse_privacy_answer(text: str) -> Literal["private", "general"] | None:
    folded = fold(text).strip()
    cleaned = _RELEASED.sub(" ", _NEGATED_PRIVACY.sub(" ", folded))
    if _PRIVATE.search(cleaned):
        return "private"
    if len(cleaned.split()) <= _SHORT_MAX_WORDS and _SHORT_PRIVATE_WORD.search(cleaned):
        return "private"
    if _MIXED.search(folded):
        return None
    if _GENERAL.search(folded) or _RELEASED.search(folded):
        return "general"
    return None


# "I told my sister to keep it to herself", "she asked me to keep it between us": somebody else's
# confidence; removed (with the rest of its clause) before the patterns run.
_THIRD_PARTY = re.compile(
    r"\b(?:told|asked|made|begged|warned|reminded|texted|tell|ask|telling|asking)\s+"
    r"(?!you\b)(?:me|him|her|them|us|my \w+|[a-z]+)\s+to\s+(?:keep|stay|not tell)\b[^.!?\n]*"
)

_EXPLICIT = re.compile(
    "|".join(
        f"(?:{p})"
        for p in (
            r"\bkeep\s+(?:this|it|that|everything)\s+(?:a\s+)?(?:to yourself|between|secret|"
            r"private|confidential|quiet|under wraps|just between|in confidence|on the "
            r"down ?low)",
            r"\bkeep\s+(?:a|my|this)\s+secret\b",
            # "between us" needs a keeping word near it: not "the distance between us"
            r"\b(?:keep|keeps|stay|stays|staying|remain|remains|just|strictly|only|please)\b"
            r"[\w' ]{0,25}\bbetween (?:us|you and me|me and you)\b",
            r"\bit's between (?:us|you and me)\b",
            r"[,.;:(-]\s*(?:just |strictly )?between (?:you and me|us)\s*[.!?)]*$",
            r"^\W*between (?:you and me|us)\b",
            r"\bdon'?t\s+(?:you\s+)?(?:tell|say|breathe a word to)\s+(?:this\s+to\s+)?"
            r"(?:anyone|anybody|a soul|nobody|no one|others|people)\b",
            r"\bdo not tell (?:anyone|anybody|a soul)\b",
            r"\bdon'?t say anything to (?:anyone|anybody|a soul)\b",
            r"\bdon'?t (?:repeat|pass on|share|spread) (?:this|that|it)\b",
            r"\bdon'?t tell (?:my|his|her|their|our)\s+\w+",
            r"\bdon'?t mention (?:this|that|it) to (?:anyone|anybody|others|people)\b",
            r"\bdon'?t let (?:anyone|anybody|people) know\b",
            r"\byou can'?t tell (?:anyone|anybody)\b",
            r"\bpromise (?:me )?(?:you(?:'ll| will| won'?t)|not to) (?:tell|say|keep)\b",
            r"\b(?:this|that) is (?:a |very |really |highly |strictly |top )*(?:secret|"
            r"private|confidential|sensitive)\b",
            r"\b(?:it'?s|that'?s) (?:a |very |really |highly |strictly )*(?:secret|private|"
            r"confidential)\b",
            r"\boff the record\b|\bin confidence\b|\bhush[- ]hush\b|\bstrictly confidential\b",
            r"\b(?:tell|share) you a secret\b|\b(?:i have|i've got|got) a secret\s*(?:[.!?:,]|$)",
        )
    )
)


def explicit_private(text: str) -> bool:
    folded = fold(text).strip()
    cleaned = _THIRD_PARTY.sub(" ", folded)
    return bool(_EXPLICIT.search(cleaned))


# A general statement made in the sensitive message itself (Berk, Phase 5: "infer first"). Only
# strong phrases: "it's fine" or "I don't mind" are too weak to loosen a category without a
# question, so they count only as an answer to one (parse_privacy_answer).
_DECLARED_GENERAL = re.compile(
    "|".join(
        f"(?:{p})"
        for p in (
            _NEGATED_PRIVACY.pattern,
            r"\bevery(?:one|body)(?:\s+\w+){0,3}\s+(?:knows?|knew|is aware)\b",
            r"\bi (?:tell|told|talk to|share (?:it )?with|show) (?:everyone|everybody|anyone|"
            r"anybody)\b",
            r"\bi\s+(?:talk|speak|discuss|joke|chat|vent|post|tell|share)\w*\b[^.!?]{0,30}\b"
            r"(?:openly|freely|all the time|publicly)\b",
            r"\bout in the open\b|\bopen book\b|\bcommon knowledge\b|\bnothing to hide\b",
            r"(?<!some )\bpeople (?:already )?know\b|\bmost people know\b",
        )
    )
)


def declared_general(text: str) -> bool:
    """True when the message itself says the topic is fine to share ("everyone knows")."""
    folded = fold(text).strip()
    if _MIXED.search(folded) or _PRIVATE.search(_NEGATED_PRIVACY.sub(" ", folded)):
        return False
    return bool(_DECLARED_GENERAL.search(folded))


# The user wants to tell someone else (Berk, Phase 5: the privacy question comes only then, on the
# same turn). Future or question forms only: "I told my sister" is past and is not intent.
_SHARE_INTENT = re.compile(
    "|".join(
        f"(?:{p})"
        for p in (
            r"\b(?:should|shall|want to|wanna|going to|gonna|plan to|like to|thinking of|"
            r"thinking about|may|might|can|could) (?:i |we )?(?:\w+ ){0,2}?"
            r"(?:tell|share|mention|bring up|talk to|talk about|let)\b",
            r"\b(?:okay|ok|fine|alright|allowed|right) (?:if i |to |for me to )"
            r"(?:tell|share|mention|bring up|talk about)\b",
        )
    )
)


def shares_with_others(text: str) -> bool:
    """True when the message says the user wants to tell someone else about something."""
    return bool(_SHARE_INTENT.search(fold(text)))
