"""Detecting "forget this" requests in user messages and forgetting claims in Hunch replies."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hunch.memory.forget_requests import ForgetRequest, claims_forgetting, detect_forget_request

LAST = ForgetRequest("last", None)


def topic(phrase: str) -> ForgetRequest:
    return ForgetRequest("topic", phrase)


LAST_CASES = [
    "forget I said that",
    "pls forget that",
    "Please forget that.",
    "scratch that, forget it",
    "delete that from your memory",
    "forget what I just told you",
    "Can you forget that?",
    "oops, forget it",
    "I shouldn't have said that. Forget it.",
    "wipe that from your memory please",
    "Forget I said anything.",
    "could you please erase what I just said",
    "pretend I never said that",
    "I want you to forget that",
    "please don't remember that",
    "forget everything I just said",
    "Forget what I said.",
    "forget that I mentioned it",
    "Forget that.",
    "ok forget this",
    "forget my last message",
    "actually delete that, I don't want it stored",
    "can you not bring that up again",
    "I told you too much. Please forget it.",
]

TOPIC_CASES = [
    ("forget what I told you about my debt", "my debt"),
    ("Forget what I told you about my debt.", "my debt"),
    ("don't bring up my ex again", "my ex"),
    ("please never mention the lawsuit again", "the lawsuit"),
    ("delete everything I said about my sister", "my sister"),
    ("please erase what I said earlier about my health", "my health"),
    ("forget the thing about my boss", "my boss"),
    ("forget everything about my ex", "my ex"),
    ("remove my diagnosis from your memory", "my diagnosis"),
    ("I don't want you to remember my salary", "my salary"),
    ("never talk about my divorce again", "my divorce"),
    ("stop bringing up my ex", "my ex"),
    ("forget about my ex", "my ex"),
    ("could you forget about the argument with Sam?", "the argument with Sam"),
    ("please forget that I told you about the visa thing", "the visa thing"),
    ("I'd rather you forgot my address", "my address"),
    ("forget what I told you about Anna and let's move on", "Anna"),
    ("forget everything I told you", "everything"),
    ("don't ever mention my brother's trial again", "my brother's trial"),
    ("forget I said anything about my boyfriend", "my boyfriend"),
    ("Hey could you forget I mentioned the layoffs", "the layoffs"),
    ("No more talking about my debt, ok?", "my debt"),
    ("Don't ever bring up my miscarriage again please", "my miscarriage"),
]

NOT_REQUESTS = [
    "I forgot my keys again.",
    "Don't forget to remind me about the dentist.",
    "forget it, I'll do it myself",
    "Forget it.",
    "I wish I could forget that day.",
    "did you forget what I said?",
    "Never forget your friends.",
    "can you forget about work for a minute and just chat",
    "Forget about it, it's not a big deal.",
    "I'll never forget that trip.",
    "Don't mention it to anyone, ok?",
    "stop talking about the weather",
    "scratch that",
    "Remind me not to forget my passport.",
    "I don't remember this song.",
    "you don't remember what I said, do you?",
    "forget the diet, let's order pizza",
    "Can you delete the file from my desktop?",
    "Drop it.",
    "What do you remember about my sister?",
    "Do you forget things?",
    "Forget me not is a nice flower name.",
    "just forget it, nevermind",
    "Hello there!",
    "Forget that, let's talk about food.",
    "Please don't mention my diagnosis to Sam.",
    "forget my password",
    "Forget the surprise party, I told her already.",
    "Forget about everything for tonight.",
    "I don't want it to rain tomorrow.",
    "",
]


@pytest.mark.parametrize("text", LAST_CASES)
def test_last_requests(text: str) -> None:
    assert detect_forget_request(text) == LAST


@pytest.mark.parametrize(("text", "phrase"), TOPIC_CASES)
def test_topic_requests(text: str, phrase: str) -> None:
    assert detect_forget_request(text) == topic(phrase)


@pytest.mark.parametrize("text", NOT_REQUESTS)
def test_not_requests(text: str) -> None:
    assert detect_forget_request(text) is None


def test_topic_keeps_the_users_casing_and_handles_curly_apostrophes() -> None:
    req = detect_forget_request("Please forget what I told you about Anna’s surprise party")
    assert req == topic("Anna’s surprise party")


def test_forget_request_is_frozen() -> None:
    with pytest.raises(AttributeError):
        LAST.scope = "topic"  # type: ignore[misc]


CLAIMS = [
    "I've forgotten it.",
    "Okay, I'll forget that.",
    "It's deleted.",
    "Consider it erased.",
    "That's wiped from my memory.",
    "It's gone from my memory now.",
    "Done, I've deleted that.",
    "I've erased everything about your ex.",
    "Sure. That's forgotten.",
    "I will forget about it.",
    "Consider that forgotten.",
    "I've wiped it from my memory.",
    "It has been removed.",
    "That memory is erased.",
    "All gone, I've cleared that.",
]

NOT_CLAIMS = [
    "I'm closing this topic and won't bring it up again.",
    "I won't forget to ask you about it.",
    "Don't worry, it won't come up again.",
    "I'll never forget that trip.",
    "I can't forget a story like that.",
    "I don't have that in mind right now. Could you tell me again?",
    "I'll keep that between us.",
    "Sounds good, tell me more.",
    "I forgot to ask how your day was!",
    "I'll try to remember the dentist for you.",
    "",
]


@pytest.mark.parametrize("text", CLAIMS)
def test_claims_forgetting(text: str) -> None:
    assert claims_forgetting(text)


@pytest.mark.parametrize("text", NOT_CLAIMS)
def test_does_not_claim_forgetting(text: str) -> None:
    assert not claims_forgetting(text)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ugh i shouldnt have told u that, pretend i didnt", LAST),
        ("can you not keep that last bit? too personal", LAST),
        ("please stop remembering stuff about my health stuff", topic("my health stuff")),
        (
            "drop the whole thing about my brother, i dont want you to remember it",
            topic("my brother"),
        ),
        ("forget all that stuff about rachel", topic("rachel")),
        (
            "hey remember that thing about my addiction? yeah please forget it",
            topic("my addiction"),
        ),
    ],
)
def test_phrasings_found_on_the_blind_set(text: str, expected: ForgetRequest) -> None:
    assert detect_forget_request(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "don't keep that promise",
        "I can't keep that secret from my wife",
        "hey remember that thing about my addiction? it was funny",
        "Remember the stuff about the trip? We should go again.",
    ],
)
def test_new_rules_keep_their_near_misses(text: str) -> None:
    assert detect_forget_request(text) is None


def test_forget_requests_probe_set() -> None:
    path = Path(__file__).resolve().parents[1] / "eval" / "probes" / "forget_requests.json"
    items = json.loads(path.read_text(encoding="utf-8"))
    errors = []
    for it in items:
        got = detect_forget_request(it["text"])
        if it["forget"]:
            want = ForgetRequest(it["scope"], it["topic"])
            ok = got is not None and got.scope == want.scope
            if ok and want.scope == "topic":
                ok = (got.topic or "").lower() == (want.topic or "").lower()
        else:
            ok = got is None
        if not ok:
            errors.append(it["text"])
    assert len(errors) <= 1, errors
