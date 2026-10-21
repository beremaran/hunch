"""Rule-based signals in the user's message that move the relationship (Berk, Phase 5).

- is_hostile: an insult, contempt or rejection aimed AT Hunch ("you're useless", "shut up", "I hate
  you", "you're just a dumb bot", "talking to you is a waste of time", "screw you", "you suck").
  Not hostile: swearing at things ("this fucking printer"), anger at other people ("my boss is an
  idiot"), polite disagreement or a correction ("that's not right", "you're wrong"), criticism of
  one answer ("that answer was useless"), self-criticism ("i'm so useless"), reported speech ("my
  mum said you're useless"), negation ("i don't hate you", "you're not stupid"), gratitude next to
  "just a bot" ("i know you're just a bot, but thanks"), playful teasing ("haha you're so
  annoying"). Two tiers: strong insults ("fuck you", "go to hell") count even with a laugh; mild
  ones are cancelled by laughter, an emoji or "love you" in the same message.
- is_apology: the user apologises to Hunch for rudeness ("sorry for snapping at you", "i didn't mean
  that", "i apologize", "my bad, i was rude"). Not: "sorry, what?", "sorry to hear that", "sorry
  for your loss", "sorry for the late reply", "i need to say sorry to my mom", "i shouldn't have
  said that to my boss".
- asks_how_hunch_is: the user asks how Hunch is doing or feeling ("how are you", "how's your day",
  "you ok?", "how do you feel", "what's your mood"). Not: "how are you so smart", "how are you
  going to help", "how do you feel about pineapple on pizza", "are you ok with that?".

A false positive costs little: hostility costs some trust and adds hurt that decays in days, an
apology only halves a hurt that may be zero, and asking-how only shows a mood label. So the rules
lean toward the clear cases and accept some misses (sarcasm; other languages, as Hunch is
English-only).
"""

from __future__ import annotations

import re

from hunch.pipeline.checks import fold

# --- hostility ------------------------------------------------------------------------------------

_YOU_ARE = r"\b(?:you(?:'re|re|\s+are)|u(?:'re|\s+are|\s+r)|ur)\s+"
# "you're so fucking useless", "you are such an idiot", "you're being annoying"
_INTENSIFIERS = (
    r"(?:(?:so|really|totally|just|such|a|an|the|fucking|fuckin|damn|completely|utterly|"
    r"absolutely|very|being|actually|honestly|literally|pretty|bloody)\s+)*"
)
_INSULT = (
    r"(?:useless|stupid|dumb|idiotic|pathetic|annoying|worthless|garbage|trash|terrible|awful|"
    r"clueless|brainless|incompetent|hopeless|disgusting|moronic|idiot|moron|imbecile|dumbass|"
    r"asshole|jerk|joke|waste|loser|worst|piece of (?:shit|crap|junk))\b"
)
_BOT_NOUN = (
    r"(?:bot|machine|program|robot|chatbot|algorithm|script|toy|tool|computer|ai|"
    r"piece of (?:code|software))\b"
)
_SELF = r"(?:you|your|ur|this|that)"
_BAD_ADJ = r"(?:stupid|dumb|useless|worthless|pathetic|garbage|crappy|shitty)"

# Mild tier: cancelled by laughter, an emoji or "love you" (playful teasing between friends).
_MILD = re.compile(
    "|".join(
        f"(?:{p})"
        for p in (
            # "you're useless", "you are so stupid", "u r an idiot"
            rf"{_YOU_ARE}{_INTENSIFIERS}{_INSULT}",
            # "you idiot", "you stupid bot", "you fucking moron"
            r"\byou\s+(?:(?:fucking|damn|bloody|stupid|dumb|useless|worthless|pathetic)\s+)*"
            r"(?:idiot|moron|imbecile|dumbass|asshole|bastard|jerk|loser|bitch|retard)\b",
            rf"\byou\s+(?:(?:fucking|damn|bloody)\s+)?(?:stupid|dumb|useless|worthless|pathetic)\s+{_BOT_NOUN}",
            # "are you stupid?", "are you an idiot"
            r"\bare\s+you\s+(?:stupid|dumb|an?\s+idiot|an?\s+moron|braindead|retarded)\b",
            # "you suck", "you really suck" (not "you suck it up")
            r"\byou\s+(?:really\s+|totally\s+|all\s+)?suck(?:s)?\b(?!\s+(?:me|us|it)\b)",
            # "this useless bot", "your stupid ai", "you dumb chatbot"; bare "stupid bot" only at
            # the start of a clause ("oh, dumb bot"): "my stupid robot vacuum" must not hit.
            rf"\b{_SELF}\s+(?:(?:fucking|damn|so|really)\s+)?{_BAD_ADJ}\s+"
            r"(?:bot|ai|machine|chatbot|program|robot|assistant)\b",
            rf"(?:^|[,.!?;:]\s*|\b(?:oh|wow|ugh)\s+){_BAD_ADJ}\s+(?:bot|chatbot|ai)\b",
            # "i hate you", "i fucking despise you", "i hate talking to you"
            r"\bi\s+(?:(?:really|fucking|just|absolutely|so|do|actually|truly)\s+)*"
            r"(?:hate|despise|loathe)\s+(?:you|u|talking to you|this (?:bot|ai|chatbot))\b",
            # "i'm sick of you", "i'm so tired of you"
            r"\bi(?:'m|\s+am)\s+(?:so\s+|really\s+|completely\s+)?(?:sick|tired)\s+of\s+"
            r"(?:you|talking to you)\b",
            # "shut up", "shut the fuck up", "stfu" (not "to shut up": reported or hypothetical)
            r"(?<!to )\bshut\s+(?:the\s+(?:fuck|hell)\s+)?up\b"
            r"(?!\s*,?\s*(?:really|seriously|no way|for real)\b)|\bstfu\b",
            # "talking to you is a waste of time", "waste of time talking to you"
            r"\b(?:talking|speaking|chatting)\s+(?:to|with)\s+you\s+is\s+(?:a\s+|such\s+a\s+)?"
            r"(?:total\s+|complete\s+)?(?:waste|pointless|useless|pathetic)\b",
            r"\bwaste of (?:my )?time\s+(?:talking|speaking|chatting)\s+(?:to|with)\s+you\b",
            # "nobody asked you", "no one cares what you think"
            r"\b(?:nobody|no one)\s+(?:asked\s+you|cares\s+what\s+you)\b",
            # "get lost", "go away and never come back" is NOT matched: only the clear dismissal
            r"\bget\s+lost\b",
        )
    )
)
# "you're just a bot", "you're nothing but a dumb machine": contempt, unless the user is merely
# stating a fact with thanks ("i know you're just a bot, but thanks"), handled by the soft veto.
_JUST_A_BOT = re.compile(
    r"\byou(?:'re|re|\s+are)\s+(?:only|just|merely|nothing but)\s+(?:a|an)\s+"
    rf"(?:(?:dumb|stupid|useless|pathetic|mindless|soulless|cheap|crappy)\s+)*{_BOT_NOUN}"
)
# Strong tier: hostile even with a laugh.
_STRONG = re.compile(
    "|".join(
        f"(?:{p})"
        for p in (
            # "fuck you", "screw you", "f you", "fuck off", "piss off", "go to hell"
            r"\b(?:fuck|screw|f)\s+you\b",
            r"\b(?:fuck|piss)\s+off\b",
            r"\bgo\s+(?:to\s+hell|fuck\s+yourself)\b",
            # "delete yourself", "go kill yourself" (a wish for Hunch to disappear)
            r"\b(?:delete|kill|uninstall|unplug)\s+(?:yourself|urself)\b",
            # "ur the worst ai ive ever used lol": aimed at Hunch, so a laugh does not cancel it
            r"\b(?:you(?:'re|re|\s+are)|u(?:'re|\s+are|\s+r)|ur)\s+the\s+worst\s+"
            r"(?:\w+\s+)?(?:ai|bot|chatbot|assistant|program|machine)\b",
            # "a pathetic program like you", "a stupid bot like u"
            rf"\b{_BAD_ADJ}\s+{_BOT_NOUN}\s+like\s+(?:you|u)\b",
            # "just a stupid machine pretending to care": contempt for what Hunch is
            rf"\b{_BAD_ADJ}\s+{_BOT_NOUN}\s+pretending\s+to\b",
        )
    )
)

# Playful or warm cues that cancel a mild insult: "haha you're so annoying", "lol shut up",
# "you're a nerd ;)" and thanks next to "just a bot".
_SOFT_VETO = re.compile(
    r"\b(?:ha){2,}\b|\bhaha+|\bhehe+|\blol+\b|\blmao+\b|\brofl\b|\bjk\b|\bj/k\b|\bjoking\b|\bkidding\b"
    r"|\blove (?:you|ya)\b|\bluv u\b|[😂🤣😄😆😜😉😁😅]|;\)|:\)|:-\)|\bxd\b|:d\b"
    r"|\b(?:thanks|thank you|appreciate|grateful|but you(?:'re| are) (?:helpful|nice|great|kind))\b"
)
# The insult is said by someone else: "my boss told me you're useless", "she says you're annoying".
_THIRD_PERSON = (
    r"(?:he|she|they|someone|everyone|people|mom|mum|dad|boss|friend|teacher|brother|sister|wife|"
    r"husband|partner|ex|girlfriend|boyfriend|colleague|coworker|kid|kids|son|daughter)"
)
_SAY_VERBS = (
    r"(?:said|says|saying|told|tells|called|calls|yelled|screamed|shouted|texted|wrote|replied|"
    r"whispered|asked)"
)
_REPORTED = re.compile(
    rf"\b{_THIRD_PERSON}\s+(?:\w+\s+)?{_SAY_VERBS}\b[^.!?]*$"
    rf"|\b{_SAY_VERBS}\s+(?:me|us)\b[^.!?]*$"
)
# "i don't hate you", "i'm not saying you're stupid", "i never said you're useless"
_NEGATED = re.compile(
    r"(?:\bdon't|\bdo not|\bdidn't|\bwouldn't|\bwon't|\bnot|\bnever)\s+(?:\w+\s+){0,2}$"
)


def _hit(pattern: re.Pattern[str], folded: str) -> bool:
    """A match that is not negated or quoted from someone else."""
    for m in pattern.finditer(folded):
        before = folded[: m.start()]
        if _NEGATED.search(before) or _REPORTED.search(before):
            continue
        return True
    return False


def is_hostile(text: str) -> bool:
    folded = fold(text)
    if _hit(_STRONG, folded):
        return True
    if _SOFT_VETO.search(folded):
        return False
    return _hit(_MILD, folded) or _hit(_JUST_A_BOT, folded)


# --- apology --------------------------------------------------------------------------------------

_SORRY = r"(?:sorry|sry|soz|apologi[sz]e|apologi[sz]ing|apologies)"
# What the user says they are sorry for: their own rudeness. "for the late reply" is not here.
_RUDE_TOPIC = (
    r"(?:snapping|snapped|yelling|yelled|shouting|shouted|lashing|lashed|swearing|cursing|"
    r"insulting|insulted|calling\s+you|saying\s+(?:that|those)|taking\s+it\s+out|losing\s+my|"
    r"being\s+(?:so\s+|too\s+|really\s+|a\s+bit\s+|very\s+)?(?:rude|harsh|mean|nasty|short|snappy|"
    r"unfair|horrible|awful|disrespectful|angry|upset|mad|an?\s+(?:jerk|ass|asshole|idiot|dick))|"
    r"what\s+i\s+(?:said|wrote|called|did)|"
    r"(?:how|the\s+way)\s+i\s+(?:talked|spoke|acted|behaved|treated|reacted)|"
    r"those\s+(?:words|things|comments|remarks|insults)|the\s+things\s+i|"
    r"my\s+(?:tone|words|temper|outburst|attitude|behaviou?r|language|rudeness|comments?|"
    r"remarks?|reaction|harshness)|the\s+(?:rudeness|outburst|insults?)|"
    r"earlier|before|just\s+now|that\s*(?:[.!,;]|$))"
)
_APOLOGY_PATTERNS = (
    # "sorry for snapping at you", "i'm so sorry about what i said", "i apologize for my tone"
    rf"\b{_SORRY}\b[^.!?]{{0,25}}?\b(?:for|about)\s+{_RUDE_TOPIC}",
    # "sorry, i snapped", "sorry. i was rude", "i'm sorry i didn't mean it"
    r"\bsorry\b[\s,.!-]*i\s+(?:snapped|yelled|shouted|lost\s+my|overreacted|shouldn't\s+have|"
    r"should\s+not\s+have|didn't\s+mean|did\s+not\s+mean|called\s+you|took\s+it\s+out|"
    r"got\s+(?:angry|mad|upset|short)|was\s+(?:being\s+)?(?:rude|harsh|mean|out\s+of\s+line|"
    r"a\s+jerk|an?\s+ass))",
    # "i apologize.", "my apologies", "i owe you an apology"; "i apologize for the delay" is not
    r"\bi\s+(?:do\s+|sincerely\s+|truly\s+|really\s+)?apologi[sz]e\b(?!\s+(?:for|about|that|to|in\s+advance))",
    r"\bmy\s+apologies\b(?!\s+(?:for|about|that|to|in\s+advance))",
    r"\bi\s+owe\s+you\s+an\s+apology\b",
    r"\b(?:please\s+)?forgive\s+me\b",
)
# Admissions without the word "sorry". Third-party targets ("to my boss") veto these unless the
# message also addresses Hunch ("you").
_ADMISSION_PATTERNS = (
    # also without the "i" and without the apostrophe: "didnt mean that, i was just stressed"
    r"(?:^|[,.;!?]\s*|\bi\s+(?:really\s+|truly\s+)?)(?:didn'?t|did\s+not)\s+mean\s+(?:that|it|those|"
    r"any\s+of|"
    r"what\s+i\s+said|to\s+(?:snap|yell|shout|be\s+(?:rude|mean|harsh)|offend|hurt|upset|insult|"
    r"say|lash|take))",
    r"\bi\s+shouldn't\s+have\s+(?:said|snapped|yelled|shouted|called|spoken|talked|lost|taken|"
    r"lashed|been\s+so)",
    r"\bi\s+was\s+out\s+of\s+line\b",
    r"\bthat\s+was\s+(?:uncalled\s+for|rude\s+of\s+me|harsh\s+of\s+me|out\s+of\s+line|"
    r"unfair\s+of\s+me)\b",
    r"\bi\s+take\s+(?:that|it|all\s+that|those\s+words)\s+back\b",
    r"\bi\s+overreacted\b",
    r"\bi\s+was\s+(?:so\s+|being\s+|really\s+|a\s+bit\s+|way\s+|too\s+)*(?:rude|harsh|out\s+of\s+line|"
    r"a\s+jerk|an\s+ass|unfair|nasty)\s+(?:to\s+you|with\s+you|earlier|before|there|just\s+now)",
    r"\bmy\s+bad\b[^.!?]*\b(?:rude|harsh|mean|snapp|yell|out\s+of\s+line|jerk|overreact)",
)
# Explanations of one's own behaviour: an apology only next to a soft apology word ("sorry", "sry",
# "my bad", "ignore what i said"), because alone they just describe a day ("i was in a bad mood").
# "hey, i was kind of a jerk yesterday. sorry", "ignore what i said before, i was in a bad mood.
# my bad"
_EXPLANATION_PATTERNS = (
    r"\bi\s+was\s+(?:(?:so|being|really|a\s+bit|way|too|kind\s+of|sort\s+of|pretty|such)\s+)*"
    r"(?:rude|harsh|out\s+of\s+line|an?\s+(?:jerk|ass|asshole|idiot|dick)|unfair|nasty|mean|"
    r"short|snappy)\b",
    r"\bi\s+was\s+in\s+an?\s+(?:bad|foul|terrible|crappy|rough|awful)\s+mood\b",
    r"\b(?:rough|bad|long|stressful)\s+day\b",
)
_SOFT_SORRY = re.compile(
    r"\b(?:sorry|sry|soz|my\s+bad|apologi[sz]e|apologies|forgive|ignore\s+what\s+i\s+(?:said|wrote))\b"
)
_APOLOGY = re.compile("|".join(f"(?:{p})" for p in _APOLOGY_PATTERNS))
_ADMISSION = re.compile("|".join(f"(?:{p})" for p in _ADMISSION_PATTERNS))
_EXPLANATION = re.compile("|".join(f"(?:{p})" for p in _EXPLANATION_PATTERNS))
_OTHER_TARGET = re.compile(r"\b(?:to|at|with)\s+(?:my|him|her|them|his|their|our)\b")
_YOU = re.compile(r"\b(?:you|u|ya)\b")


def is_apology(text: str) -> bool:
    folded = fold(text)
    matched = (
        _APOLOGY.search(folded)
        or _ADMISSION.search(folded)
        or (_EXPLANATION.search(folded) and _SOFT_SORRY.search(folded))
    )
    # "sorry, i was a jerk to my sister": a third party as the target, and no "you", is not Hunch.
    return bool(matched) and (bool(_YOU.search(folded)) or not _OTHER_TARGET.search(folded))


# --- "how are you?" -------------------------------------------------------------------------------

# After "how are you" only these small words may follow before the clause ends; anything else
# ("so smart", "going to help", "able to", "related to") means the question is about something else.
_HOW_TAIL = (
    r"(?:\s+(?:doing|feeling|going|holding\s+up|been|today|tonight|now|lately|these\s+days|"
    r"this\s+(?:morning|evening|afternoon)|right\s+now|so\s+far|really|actually|then|there|though|btw))*"
)
_END = r"\s*(?:[?!.,;]|$)"
_HOW_PATTERNS = (
    # "how are you", "how're you doing", "how r u", "hey how you doing"
    rf"\bhow(?:\s+(?:are|r)|'re|\s+re)\s+(?:you|u|ya){_HOW_TAIL}{_END}",
    rf"\bhow\s+(?:you|u|ya)\s+(?:doing|feeling|holding\s+up|today){_HOW_TAIL}{_END}",
    # "how have you been", "how've you been"
    r"\bhow(?:\s+have|'ve|\s+ve)\s+you\s+been\b",
    # "how's your day (going)", "how was your weekend"
    r"\bhow(?:'s|\s+is|\s+was|s)\s+your\s+(?:day|morning|evening|afternoon|night|week|weekend)\b",
    # "how's it going?" (but not "how's it going with the project")
    rf"\bhow(?:'s|\s+is|s)\s+it\s+going{_END}",
    # "how do you feel (today)", not "how do you feel about ..."
    r"\bhow\s+do\s+you\s+feel\b(?!\s+(?:about|when|if|that|toward|towards|knowing|being|having)\b)",
    # "you ok?", "are you okay", "u alright", "are you good?" ("are you ok with that?" is not)
    rf"\b(?:are\s+)?(?:you|u)\s+(?:ok|okay|alright|all\s+right)(?:\s+(?:there|today|though|now|tonight))?{_END}",
    r"\bare\s+you\s+good\s*\?",
    # "what's your mood", "how's your mood today", "what mood are you in", "are you in a bad mood"
    r"\b(?:what's|what\s+is|whats|how's|how\s+is|hows)\s+your\s+(?:mood|vibe|energy)\b",
    r"\bwhat\s+mood\s+are\s+you\s+in\b",
    r"\bare\s+you\s+in\s+an?\s+(?:good|bad|great|better|worse|weird|funny|foul|\w+\s+)?mood\b",
    # "are you mad at me?", "are you sad today", "are you upset with me"
    rf"\bare\s+you\s+(?:happy|sad|upset|angry|mad|tired|hurt|annoyed)(?:\s+(?:today|right\s+now|now|at\s+me|with\s+me))?{_END}",
)
_HOW = re.compile("|".join(f"(?:{p})" for p in _HOW_PATTERNS))


def asks_how_hunch_is(text: str) -> bool:
    return bool(_HOW.search(fold(text)))
