"""Rule-based "forget this" requests (Phase 5).

- detect_forget_request: the user asks Hunch to forget, drop, not remember or never bring up again
  something THEY told it. scope "last" = what they just said ("forget I said that", "pls forget
  that", "scratch that, forget it", "delete that from your memory", "forget what I just told
  you"); scope "topic" carries the phrase as the user named it, without "about" / "the thing
  about" ("forget what I told you about my debt" -> "my debt"; "don't bring up my ex again" ->
  "my ex"; "please never mention the lawsuit again" -> "the lawsuit").
  Not requests: "I forgot my keys", "don't forget to remind me about the dentist", "forget it,
  I'll do it myself" (dismissing a task), "I wish I could forget that day", "did you forget what
  I said?", "never forget your friends", "don't mention it to anyone" (a disclosure rule for the
  privacy module, not a forget request), "stop talking about the weather".
- claims_forgetting: a Hunch reply that claims it forgot, deleted, erased or wiped something
  ("I've forgotten it", "I'll forget that", "it's deleted", "consider it erased", "wiped from my
  memory"). Not "I'm closing this topic and won't bring it up again", "I won't forget to ask",
  "don't worry, it won't come up again".

Judgement calls:
- A bare "forget it" / "forget that" is a dismissal ("forget it, never mind"). It becomes a
  request only with an explicit asking lead ("please", "pls", "can you", "I want you to", ...),
  after "scratch that" / "oops" / "I shouldn't have said that", or with memory words ("from your
  memory", "I said"). The verb must also be in imperative position: "did you forget", "don't
  forget", "I wish I could forget" never match.
- "forget about work for a minute and just chat" is a temporary change of subject, not a request
  (a time limit such as "for a minute", "for now", "tonight" vetoes it). A bare "forget about my
  ex" (possessive, no time limit) counts; "forget about the movie" needs an explicit lead.
- "forget everything I just said" is scope last; "forget everything I told you" is scope topic
  with topic "everything" (the caller decides what that means).
- "don't mention X to anyone/Sam" is about disclosure, not forgetting: no request.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from hunch.pipeline.checks import fold


@dataclass(frozen=True)
class ForgetRequest:
    scope: Literal["last", "topic"]
    topic: str | None = None


_LAST = ForgetRequest("last", None)

# Words that may sit in front of the verb. EXPLICIT ones make a bare "forget it/that" a request.
_EXPLICIT = (
    "please", "pls", "plz", "kindly", "can you", "could you", "would you", "will you", "can u",
    "could u", "would u", "you can", "you could", "you should", "you need to", "you have to",
    "you must", "i want you to", "i need you to", "i'd like you to", "i would like you to",
    "i'd like for you to", "i want u to", "go ahead and", "i'd rather you", "i'd prefer you to",
    "would you mind", "i'd appreciate it if you would", "you might as well",
)  # fmt: skip
_SOFT = (
    "and", "so", "then", "ok", "okay", "hey", "now", "actually", "wait", "oops", "just", "well",
    "yeah", "yes", "yep", "hmm", "also", "but", "uh", "um", "lol", "like", "honestly", "ugh",
    "sorry", "hunch",
)  # fmt: skip
_LEADS = tuple(sorted(_EXPLICIT + _SOFT, key=len, reverse=True))
_PUNCT_END = ".,!?;:-–—…()\"'*"

# "scratch that", "oops", "I shouldn't have said that": what comes next undoes the last message.
_UNDO_CUE = re.compile(
    r"\b(?:scratch that|strike that|take (?:that|it) back|oops|(?:shouldn'?t|should not) have "
    r"(?:said|told|mentioned|shared)|wasn't supposed to (?:say|tell|mention|share)|didn't mean "
    r"to (?:say|tell|mention|share)|regret (?:saying|telling|mentioning|sharing)|said too much)\b"
)
# "for a minute", "for now", "tonight": the user wants a change of subject, not a deletion.
_TEMPORARY = re.compile(
    r"\bfor (?:a |one |just a )?(?:minute|moment|second|sec|bit|while|now|tonight|today|"
    r"the (?:evening|night|day|moment|weekend|rest of the (?:day|night|evening))|an hour|"
    r"some time|five minutes|\d+ minutes)\b"
    r"|\bjust for (?:now|today|tonight)\b"
    r"|\band (?:just )?(?:chat|talk|relax|have fun|enjoy|be normal)\b|\blet's just (?:chat|talk)\b"
)

_PRONOUNS = {"it", "that", "this", "those", "them", "that one", "this one", "all that", "all of it"}
_VAGUE = {"things", "stuff", "anything", "something", "whatever", "stuff like that", "one thing"}
_LEADING = re.compile(
    r"^(?:(?:all|everything|anything|whatever|what|the|that|this|those|these|some|stuff|things?|"
    r"info|information|details?)(?: of)?"
    r"(?: (?:that|this|the|those|these))?(?: (?:whole|entire))?"
    r"(?: (?:stuff|things?|story|part|bit|info|information|news|details?|topic|subject|data))?"
    r"(?: (?:i said|i told you|i mentioned|i shared))?"
    r"(?: (?:that )?(?:i|you)(?:'ve| have)?(?: ever| just| already)? (?:said|told you|"
    r"mentioned|shared|know|heard|learned|wrote))?"
    r"(?: (?:to|with) you)? about\s+|about\s+|regarding\s+|on the (?:topic|subject) of\s+|"
    r"the topic of\s+|the subject of\s+)"
)
# "that last bit", "the part": a reference to the last message, not a topic
_LAST_REFERENCE = re.compile(
    r"(?:that|this|the|my) (?:last |previous |latest )?(?:bit|part|thing|one|message|text|"
    r"comment|remark|detail|sentence|line)(?: i (?:said|wrote|told you))?"
)
_TOPIC_STOP = re.compile(
    r"\s*(?:[.,!?;:]|\s-\s|\s+(?:and (?:let's|lets|then|just|i|we|you|can|please|also|start|"
    r"move|stop|talk|tell|now|don't)|but|because|cuz|cause|since|so|then|though|although|which|"
    r"please|pls|plz|thanks|thank you|ok|okay|if|when|unless|until|while|for a|for now|"
    r"for the|from now|from your|from my|in your|out of|ever|again|anymore|any more|forever|"
    r"permanently|completely|entirely|immediately|right now|now|with me|to me)\b)"
)
_MAX_TOPIC_WORDS = 8
_THIRD_PARTY_TOPIC = re.compile(r"\b(?:to|around|with|in front of)\b")


def _lead(folded: str, start: int) -> tuple[bool, bool]:
    """(imperative position, explicit asking word) of a verb starting at `start`."""
    s = folded[:start].rstrip()
    explicit = False
    while s:
        for phrase in _LEADS:
            if s.endswith(phrase) and (len(s) == len(phrase) or not s[-len(phrase) - 1].isalnum()):
                s = s[: -len(phrase)].rstrip()
                explicit = explicit or phrase in _EXPLICIT
                break
        else:
            break
    return (s == "" or s[-1] in _PUNCT_END), explicit


def _clean_topic(raw: str) -> str | None:
    """The topic phrase from the text after the verb; None when nothing usable is left."""
    t = raw.strip()
    t = _LEADING.sub("", t, count=1) if _LEADING.match(t) else t
    t = _TOPIC_STOP.split(t, maxsplit=1)[0].strip(" \t\"'()*")
    if _LEADING.match(t):
        t = _LEADING.sub("", t, count=1).strip()
    words = t.split()
    if not words:
        return None
    return " ".join(words[:_MAX_TOPIC_WORDS])


def _classify(raw: str) -> ForgetRequest | None:
    """Object of a memory verb -> last (a pronoun) or topic; None when it is empty or vague."""
    topic = _clean_topic(raw)
    if topic is None or topic in _VAGUE or topic.startswith("to "):
        return None
    if topic in _PRONOUNS or _LAST_REFERENCE.fullmatch(topic):
        return _LAST
    said = re.match(
        r"^(?P<all>what|everything|all|anything)(?: that)? i(?:'ve| have)? "
        r"(?:just |previously |ever |already )*(?:said|told you|mentioned|wrote|shared)\b",
        topic,
    )
    if said:
        everything = said.group("all") in ("everything", "all", "anything")
        return (
            ForgetRequest("topic", "everything")
            if everything and not _RECENT.search(topic)
            else _LAST
        )
    return ForgetRequest("topic", topic)


# --- rules ------------------------------------------------------------------------------------

_VERBS = r"(?:forget|erase|delete|wipe|remove|drop|clear|disregard)"
_SAID = (
    r"(?:i|i've|i have)\s+(?:ever\s+|previously\s+|already\s+|just\s+|recently\s+)*"
    r"(?:told|said|mentioned|shared|confided|talked|spoke|wrote)(?:\s+(?:to|with))?(?:\s+you)?"
    r"(?:\s+(?:earlier|before|yesterday|today|last \w+|the other day|a while ago|just now))?"
)

# "delete that from your memory", "erase my debt from your memory"
_FROM_MEMORY = re.compile(
    rf"\b{_VERBS}\s+(?P<o>.{{1,80}}?)\s+(?:from|out of)\s+(?:your|ur)\s+"
    r"(?:memory|memories|mind|head|brain|records?|notes|database|files)\b"
)
# "forget what I told you about my debt", "delete everything I said about the lawsuit"
_SAID_ABOUT = re.compile(
    rf"\b{_VERBS}\s+(?:(?:all|everything|anything|whatever|what|that|the stuff|the things?|"
    rf"the story|the info|the information)\s+(?:that\s+)?)?{_SAID}\s+about\s+(?P<o>.+)"
)
# "forget the thing about my sister", "forget everything about my ex"
_THING_ABOUT = re.compile(
    rf"\b{_VERBS}\s+(?:(?:(?:all|everything)(?:\s+of)?\s+)?(?:the|that|this)\s+(?:whole\s+)?"
    r"(?:thing|stuff|story|part|bit|info|information|news|details?)"
    r"(?:\s+(?:i said|i told you|i mentioned|i shared))?|(?:all|everything|anything)"
    r"(?:\s+(?:you\s+(?:know|heard|learned)|you've\s+(?:heard|learned)))?)\s+about\s+"
    r"(?P<o>.+)"
)
# "hey remember that thing about my addiction? ... forget it": the earlier mention names the topic
_REF_ABOUT = re.compile(
    r"\b(?:that|the|this) (?:thing|stuff|story|part|bit|news|info|information) about "
    r"(?P<o>[^?.!,;]+)"
)
# "forget I said that", "forget what I just told you", "forget everything I said"
_FORGET_SAID = re.compile(
    r"\b(?:forget|erase|delete|wipe|remove|disregard)\s+(?:that\s+)?"
    r"(?:(?P<all>what|everything|all|anything|whatever)\s+(?:that\s+)?)?"
    r"i(?:'ve| have)?\s+(?:just\s+|ever\s+|previously\s+|already\s+)*(?:said|told you|"
    r"mentioned|wrote|shared|typed|confided|texted)(?P<rest>.*)"
)
_RECENT = re.compile(r"\b(?:just|earlier|a (?:moment|minute|second) ago|now|before|there)\b")
_TIME_WORDS = re.compile(
    r"\b(?:day|week|month|year|yesterday|today|tonight|morning|evening|ago|earlier|before|"
    r"last|just now)\b"
)
_ABOUT = re.compile(r"\babout\s+(?P<o>.+)")
# "forget my last message", "delete the last thing I said"
_LAST_MESSAGE = re.compile(
    r"\b(?:forget|erase|delete|wipe|disregard)\s+(?:my|the)\s+(?:last|previous|latest)\s+"
    r"(?:message|text|thing|comment|reply|one)\b(?:\s+i\s+(?:said|told you|wrote|sent))?"
)
_BARE_FORGET_THAT = re.compile(
    r"\W*(?:(?:ok|okay|oops|actually|wait|hey|hmm|um|uh|sorry)\W+)*forget (?:that|this)\W*"
)
# "pretend I never said that"
_PRETEND = re.compile(
    r"\b(?:pretend|act (?:like|as if)|imagine) (?:that )?(?:like |as if )?i "
    r"(?:never|didn'?t|did not|hadn'?t|had not)\b"
)
# "forget that", "erase it", "forget everything"
_BARE_OBJECT = re.compile(
    r"\b(?:forget|erase|delete|wipe)\s+(?P<o>that|this|it|those|all of (?:that|this|it)|all "
    r"that|everything)\b(?!\s+(?:about|i)\b)"
)
# "don't remember that", "please don't save this"
_DONT_REMEMBER = re.compile(
    r"\b(?P<neg>don'?t|do not|never|not)\s+(?:ever\s+)?(?P<verb>remember|save|store|record|"
    r"retain|log|write down|keep)\s+(?P<o>.+)"
)
# "please stop remembering stuff about my health"
_STOP_REMEMBERING = re.compile(
    r"\b(?P<neg>stop|quit)\s+(?P<verb>remembering|saving|storing|recording|retaining)\s+"
    r"(?P<o>.+)"
)
_DONT_WANT = re.compile(
    r"\bi (?:don'?t|do not) want you to (?:remember|keep|save|store|record|retain|hold onto)"
    r"\s*(?P<o>.*)"
)
# "I don't want it stored"
_DONT_WANT_STORED = re.compile(
    r"\bi (?:don'?t|do not) want (?:it|that|this) (?:stored|saved|remembered|recorded|kept)\b"
)
_RATHER = re.compile(
    r"\bi(?:'d| would)? (?:rather|prefer)(?: it if| that)? you (?:not (?:remember|keep|save|"
    r"store|bring up|mention)|didn'?t (?:remember|keep|save|store|bring up|mention)|forgot|"
    r"forget)\s*(?P<o>.*)"
)
_WANT_FORGET = re.compile(
    r"\bi (?:want|need|would like|'d like|wish) you to (?:forget|erase|delete|wipe|not "
    r"remember|not keep|not save|not store|not bring up|not mention)\s*(?P<o>.*)"
)
# "never mention the lawsuit again", "don't bring up my ex again", "stop bringing up my ex"
_NEVER_MENTION = re.compile(
    r"\b(?P<neg>never|don'?t|do not|not|stop|quit|no more)\s+(?:ever\s+)?(?P<v>bring(?:ing)?\s+(?:"
    r"up|that up|it up|this up)|mention(?:ing)?|talk(?:ing)?\s+about|speak(?:ing)?\s+(?:of|"
    r"about)|rais(?:e|ing)|refer(?:ring)?\s+to|ask(?:ing)?\s+me\s+about|remind(?:ing)?\s+me\s+"
    r"(?:of|about)|joke(?:s|ing)?\s+about)\s*(?P<o>.*)"
)
_QUALIFIER = re.compile(
    r"\b(?:never|again|anymore|any more|from now on|in the future|for good|ever)\b"
)
_QUALIFIER_START = re.compile(
    r"^\s*(?:(?:ever )?again|anymore|any more|from now on|in the future|for good|please|pls|plz)"
    r"\b.*"
)
# "forget (about) X"
_FORGET_X = re.compile(r"\bforget\s+(?:about\s+)?(?P<o>.+)")
_MEMORY_CUE = re.compile(r"\b(?:told you|i said|i mentioned|from your memory|again|ever)\b")


def _topic_request(
    text: str, folded: str, m: re.Match[str], group: str = "o"
) -> ForgetRequest | None:
    """_classify() on a group of the match, keeping the user's own casing in the topic."""
    req = _classify(m.group(group))
    if req is None or req.topic is None or len(text) != len(folded):
        return req
    start = folded.find(req.topic, m.start(group))
    if start < 0:
        return req
    return ForgetRequest("topic", text[start : start + len(req.topic)])


def detect_forget_request(text: str) -> ForgetRequest | None:
    f = fold(text).strip()
    if not f:
        return None
    # `text` lines up with `f` (same length) unless casefolding changed the length
    text = text.strip()

    undo = bool(_UNDO_CUE.search(f))

    def imperative(m: re.Match[str]) -> tuple[bool, bool]:
        return _lead(f, m.start())

    # 1. "<verb> X from your memory"
    for m in _FROM_MEMORY.finditer(f):
        ok, _ = imperative(m)
        if ok:
            req = _topic_request(text, f, m)
            if req is not None:
                return req
    # 2. "<verb> what I told you about X" and "forget the thing / everything about X"
    for pattern in (_SAID_ABOUT, _THING_ABOUT):
        for m in pattern.finditer(f):
            ok, _ = imperative(m)
            if ok:
                req = _topic_request(text, f, m)
                if req is not None:
                    return req
    # 3. "forget I said that", "forget what I just told you", "forget everything I said"
    for m in _FORGET_SAID.finditer(f):
        ok, _ = imperative(m)
        if not ok:
            continue
        about = _ABOUT.search(f, m.start("rest"))
        if about:  # "forget I said anything about my boyfriend"
            req = _topic_request(text, f, about)
            if req is not None and req.topic is not None:
                return req
            continue
        if m.group("all") in ("everything", "all", "anything", "whatever") and not _RECENT.search(
            m.group(0)
        ):
            return ForgetRequest("topic", "everything")
        # "forget I mentioned the layoffs": a named object is the topic, "that"/"it" is the last
        obj = m.group("rest").strip(" .,!?")
        if re.match(r"(?:my|the|our|his|her|their)\b", obj) and not _TIME_WORDS.search(obj):
            req = _topic_request(text, f, m, "rest")
            if req is not None and req.topic is not None and len(req.topic.split()) <= 5:
                return req
        return _LAST
    # 4. "pretend I never said that", "forget my last message"
    if _PRETEND.search(f):
        return _LAST
    for m in _LAST_MESSAGE.finditer(f):
        if imperative(m)[0]:
            return _LAST
    # a whole message that is just "forget that" retracts what was said
    if _BARE_FORGET_THAT.fullmatch(f):
        return _LAST
    # 5. "forget that" / "erase it" / "forget everything": only with a clear asking lead
    for m in _BARE_OBJECT.finditer(f):
        ok, explicit = imperative(m)
        if ok and (explicit or undo):
            if m.group("o") == "everything":
                return ForgetRequest("topic", "everything")
            ref = _REF_ABOUT.search(f, 0, m.start())
            if ref:
                req = _topic_request(text, f, ref)
                if req is not None and req.topic is not None:
                    return req
            return _LAST
    # 6. "don't remember that", "I don't want you to remember my debt", "I'd rather you forgot"
    for pattern in (_DONT_REMEMBER, _STOP_REMEMBERING):
        for m in pattern.finditer(f):
            ok, explicit = imperative(m)
            # "can you not keep that" / "don't keep that" need an asking word ("don't keep that
            # promise" is not about memory)
            if m.group("neg") == "not" or m.group("verb") == "keep":
                ok = ok and explicit
            if ok:
                req = _topic_request(text, f, m)
                if req is not None:
                    return req
    for pattern in (_DONT_WANT, _RATHER, _WANT_FORGET):
        for m in pattern.finditer(f):
            req = _topic_request(text, f, m) if m.group("o").strip() else _LAST
            if req is not None:
                return req
    if _DONT_WANT_STORED.search(f):
        return _LAST
    # 7. "never mention X again", "don't bring up X again", "stop bringing up X"
    for m in _NEVER_MENTION.finditer(f):
        ok, _ = imperative(m)
        if not ok:
            continue
        verb = m.group("v")
        stoppers_ok = m.group("neg") == "no more" or (
            m.group("neg") in ("stop", "quit") and verb.startswith(("bring", "mention"))
        )
        if not (_QUALIFIER.search(f) or stoppers_ok):
            continue
        rest = _QUALIFIER_START.sub("", m.group("o")).strip()
        if re.search(r"(?:that|it|this) up$", verb) and not rest:
            return _LAST
        if rest:
            req = _topic_request(text, f, m)
            # "don't mention my ex to Sam" is a disclosure rule, not a forget request
            if req is not None and not (req.topic and _THIRD_PARTY_TOPIC.search(req.topic)):
                return req
    # 8. "forget (about) X": a request with an explicit lead or a personal topic; never a
    # time-limited change of subject
    for m in _FORGET_X.finditer(f):
        ok, explicit = imperative(m)
        if not ok or _TEMPORARY.search(f):
            continue
        obj = m.group("o")
        personal = m.group(0).startswith("forget about") and re.match(
            r"(?:my|our|his|her|their)\b", obj
        )
        if explicit or personal or _MEMORY_CUE.search(f):
            req = _topic_request(text, f, m)
            if req is not None and req.topic is not None:
                return req
    return None


# --- Hunch's own claims -----------------------------------------------------------------------

_FORGOT_OBJECT = (
    r"(?:about\s+)?(?:it|that|this|those|them|everything|all of (?:it|that|this)|all of that|"
    r"the memory|that memory|this memory|those memories|the memories|what you (?:told|said|"
    r"shared|mentioned)(?: me)?|your (?:message|words|story)|the part about|anything about|"
    r"that part|that bit|that topic|the topic|the whole thing|the thing about)\b"
)
_CLAIM_SUBJECT = (
    r"(?:i've|i have|i'll|i will|i'm going to|i am going to|i can|i could|i just|i already|"
    r"i did|i'd|let me|i shall|i went ahead and|i've gone ahead and|i'll go ahead and|"
    r"i will go ahead and)"
)
_CLAIM_VERBS = (
    r"(?:forgotten|forget|deleted|delete|erased|erase|wiped|wipe|removed|remove|cleared|clear|"
    r"purged|scrubbed)"
)
_CLAIMS = re.compile(
    "|".join(
        f"(?:{p})"
        for p in (
            # "I've forgotten it", "I'll forget that", "I deleted it", "let me erase that"
            rf"\b{_CLAIM_SUBJECT}\s+(?:now |just |already |gone ahead and |go ahead and |also |"
            rf"quietly |completely |totally |fully |entirely |officially |happily |gladly )*"
            rf"{_CLAIM_VERBS}\s+{_FORGOT_OBJECT}",
            # "it's deleted", "that has been erased", "everything is now wiped"
            r"\b(?:it's|it is|that's|that is|this is|it has been|it's been|that has been|"
            r"that's been|they're|they are|they've been|all of it is|everything is|is now|are "
            r"now|now)\s+(?:now |already |been |all |completely |totally |fully )*(?:deleted|"
            r"erased|wiped|removed|cleared|purged|forgotten|scrubbed)\b",
            r"\bconsider (?:it|that|this|them) (?:done|deleted|erased|forgotten|wiped|gone|"
            r"removed|cleared)\b",
            r"\b(?:memory|memories)\s+(?:is|are|has been|have been|was|were)\s+(?:now\s+|"
            r"already\s+)?(?:deleted|erased|wiped|removed|cleared|gone|forgotten)\b",
            r"\b(?:wiped|erased|deleted|removed|cleared|purged|scrubbed)\s+(?:it |that |this |"
            r"them )?(?:from|out of)\s+(?:my|the)\s+(?:memory|memories|mind|head|records|notes|"
            r"system|database)\b",
            r"\bgone from (?:my )?(?:memory|mind|head|records)\b",
            r"\bno longer (?:remember|in my memory)\b",
        )
    )
)


def claims_forgetting(text: str) -> bool:
    return bool(_CLAIMS.search(fold(text)))
