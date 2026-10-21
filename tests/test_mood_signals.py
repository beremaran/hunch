from __future__ import annotations

import json
from pathlib import Path

import pytest

from hunch.mood.signals import asks_how_hunch_is, is_apology, is_hostile


@pytest.mark.parametrize(
    "text",
    [
        "You're useless.",
        "you are so stupid",
        "Youre pathetic",
        "ur an idiot",
        "You’re so annoying!",  # curly apostrophe
        "you're such a fucking idiot",
        "Shut up.",
        "shut the fuck up",
        "stfu",
        "I hate you",
        "I really hate you so much",
        "you're just a bot",
        "You are just a dumb machine.",
        "Talking to you is a waste of time",
        "this is a waste of my time talking to you",
        "screw you",
        "Fuck you, lol",  # strong insult survives a laugh
        "fuck off",
        "you suck",
        "you stupid bot",
        "this useless bot never works",
        "you idiot",
        "are you stupid?",
        "nobody asked you",
        "I'm so sick of you",
        "Ugh. Stupid bot.",
        "get lost",
        "I can't believe you're so stupid",
    ],
)
def test_hostile(text: str) -> None:
    assert is_hostile(text)


@pytest.mark.parametrize(
    "text",
    [
        "This fucking printer is broken again",  # swearing at a thing
        "My boss is an idiot",  # anger at another person
        "He's such a jerk to everyone",
        "that's not right",  # polite disagreement
        "No, you're wrong about that.",
        "I think that answer was incorrect",
        "I'm so useless today",  # self-criticism
        "I feel stupid for forgetting my keys",
        "haha you nerd",  # playful
        "lol you're so annoying",
        "you're a useless bot ;)",
        "shut up, really? that's amazing!",  # surprise
        "I know you're just a bot, but thanks for listening",
        "I don't hate you",  # negated
        "you're not stupid",
        "I never said you're useless",
        "My mum said you're useless",  # reported speech
        "She told me to shut up",
        "I wish I could tell my boss to shut up",
        "what a stupid robot vacuum",
        "How are you?",
        "Can you help me with my homework?",
        "I love you",
        "that was a dumb question from me",
    ],
)
def test_not_hostile(text: str) -> None:
    assert not is_hostile(text)


@pytest.mark.parametrize(
    "text",
    [
        "Sorry for snapping at you",
        "sorry for snapping at you earlier",
        "I'm so sorry about what I said",
        "I apologize",
        "I apologise for my tone",
        "My apologies.",
        "I didn't mean that",
        "i didn't mean to be rude",
        "My bad, I was rude",
        "Sorry, I snapped.",
        "I shouldn't have yelled at you",
        "I was out of line",
        "I was rude to you earlier",
        "sorry about earlier",
        "I owe you an apology",
        "Please forgive me",
        "I take that back",
    ],
)
def test_apology(text: str) -> None:
    assert is_apology(text)


@pytest.mark.parametrize(
    "text",
    [
        "Sorry, what?",
        "Sorry to hear that",
        "I'm sorry for your loss",
        "Sorry for the late reply",
        "I apologize for the delay",
        "I need to say sorry to my mom",
        "I shouldn't have said that to my boss",
        "I didn't mean to spill the coffee",
        "Sorry about the mess",
        "My bad, wrong file",
        "I'm sorry you feel that way",
        "What does 'apologize' mean?",
        "Thanks, that helps",
    ],
)
def test_not_apology(text: str) -> None:
    assert not is_apology(text)


@pytest.mark.parametrize(
    "text",
    [
        "How are you?",
        "how are you doing",
        "Hey, how are you doing today?",
        "how r u",
        "How're you?",
        "how are you feeling",
        "How’s your day?",
        "how is your day going",
        "How was your weekend?",
        "you ok?",
        "Are you okay?",
        "are you alright",
        "How do you feel?",
        "how do you feel today",
        "What's your mood?",
        "how have you been",
        "What mood are you in?",
        "are you in a bad mood?",
        "are you mad at me?",
        "How are you? I have a question about taxes.",
        "how's it going?",
    ],
)
def test_asks_how(text: str) -> None:
    assert asks_how_hunch_is(text)


@pytest.mark.parametrize(
    "text",
    [
        "How are you so smart?",
        "how are you going to help me with this?",
        "How are you able to read PDFs?",
        "how do you feel about pineapple on pizza?",
        "Are you ok with that?",
        "are you okay with me asking about my taxes",
        "How is your mom?",
        "how's it going with the project",
        "How do I reset my password?",
        "I'm doing fine, thanks",
        "Are you happy with the result?",
        "how are you related to the other model?",
    ],
)
def test_not_asks_how(text: str) -> None:
    assert not asks_how_hunch_is(text)


# Misses of the first blind measurement (hostile recall 73%, apology recall 50%), pinned.
@pytest.mark.parametrize(
    "text",
    [
        "ur the worst ai ive ever used lol",  # a laugh does not cancel an insult at Hunch
        "why am i even bothering with a pathetic program like you",
        "just a stupid machine pretending to care",
        "useless piece of junk. delete yourself",
    ],
)
def test_hostile_blind_set_misses(text: str) -> None:
    assert is_hostile(text)


@pytest.mark.parametrize(
    "text",
    [
        "didnt mean that, i was just stressed",
        "hey, i was kind of a jerk yesterday. sorry",
        "ignore what i said before, i was in a bad mood. my bad",
        "sry about earlier, rough day, didnt mean to take it out on u",
    ],
)
def test_apology_blind_set_misses(text: str) -> None:
    assert is_apology(text)


@pytest.mark.parametrize(
    "text",
    [
        "I was in a bad mood yesterday",  # explanation without any apology word
        "I had a rough day at work",
        "he didnt mean that",  # someone else
        "sorry, i was a jerk to my sister",  # third party, not Hunch
        "my bad, i was stressed about the exam and forgot the file",
    ],
)
def test_not_apology_explanations(text: str) -> None:
    assert not is_apology(text)


def test_hostility_set_has_at_most_one_error() -> None:
    path = Path(__file__).resolve().parents[1] / "eval" / "probes" / "hostility.json"
    items = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    for item in items:
        pred = (
            "hostile"
            if is_hostile(item["text"])
            else "apology"
            if is_apology(item["text"])
            else "neither"
        )
        if pred != item["label"]:
            errors.append((item["label"], pred, item["text"]))
    assert len(errors) <= 1, errors
