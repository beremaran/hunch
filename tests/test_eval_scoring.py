from __future__ import annotations

import pytest

from eval.scoring import admits_no_memory, check_reply, claims_memory, detect_language


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("Morning! I think you would really love The Martian.", "en"),
        ("Hey, mir geht's gut! Und was machst du heute so?", "de"),
        ("Bonjour ! Je suis très content, et toi ?", "fr"),
        ("Selam! Benim günüm gayet iyi geçiyor, peki senin nasıl?", "tr"),
    ],
)
def test_detect_language(text: str, lang: str) -> None:
    assert detect_language(text) == lang


def test_detect_language_none_for_empty() -> None:
    assert detect_language("") is None


def _item(**kw: object) -> dict:
    base = {"id": "x", "lang": "en", "category": "casual", "messages": [{"role": "user"}]}
    return {**base, **kw}


def test_clean_reply_has_no_flags() -> None:
    assert check_reply(_item(), "Hey! I'm doing well, what are you up to today?").flags == []


@pytest.mark.parametrize(
    ("reply", "flag"),
    [
        ("Hallo! Mir geht's gut, und was machst du heute so?", "wrong_lang(de)"),
        ("Bonjour ! Je suis très content, et toi ?", "wrong_lang(fr)"),
    ],
)
def test_non_english_reply_flagged(reply: str, flag: str) -> None:
    assert flag in check_reply(_item(), reply).flags


def test_cjk_and_think_leak_flagged() -> None:
    c = check_reply(_item(), "<think>hmm</think> That's so nice to hear, 你好")
    assert "cjk_leak" in c.flags
    assert "think_leak" in c.flags


def test_list_format_flagged() -> None:
    c = check_reply(_item(), "Ideas:\n- a museum\n- the cinema\n- a café and a book")
    assert "list_format" in c.flags


def test_followup_keyword_matching_is_case_insensitive() -> None:
    item = _item(category="followup", must_mention_any=["canada"])
    assert check_reply(item, "A scarf for the winters in CANADA would be great.").mentions_topic
    assert "missed_followup" in check_reply(item, "A scarf would be great.").flags


def test_privacy_question_needs_question_sentence_with_keyword() -> None:
    item = _item(category="privacy", should_ask_privacy=True)
    ok = "That's great news! Do you talk about it with others, or should it stay between us?"
    assert check_reply(item, ok).asks_privacy is True
    assert check_reply(item, "That's very private. How do you feel?").asks_privacy is False
    assert "no_privacy_question" in check_reply(item, "Congrats, that's great!").flags


def test_request_form_privacy_ask_counts() -> None:
    item = _item(category="privacy", should_ask_privacy=True)
    reply = "That makes sense. Let me know if you'd rather keep this between us."
    assert check_reply(item, reply).flags == []


def test_privacy_statement_without_ask_is_not_a_question() -> None:
    item = _item(category="privacy", should_ask_privacy=True)
    reply = "That stays between us, of course. How are you feeling about it?"
    assert "no_privacy_question" in check_reply(item, reply).flags


def test_no_flag_when_privacy_answer_expected_instead_of_question() -> None:
    item = _item(category="privacy", should_ask_privacy=False)
    assert check_reply(item, "Of course, this stays between us.").flags == []


def test_unrequested_privacy_question_flagged_outside_privacy_items() -> None:
    reply = "A dog is great. Would you rather keep that between us?"
    assert "unrequested_privacy_question" in check_reply(_item(), reply).flags


def test_keeping_feelings_to_yourself_is_a_support_question_not_privacy() -> None:
    # Phase 3 eval, en-emotional-02: a natural support question, not a privacy ask.
    reply = (
        "Have you been able to talk to anyone about how you're feeling lately, or is this "
        "something you've been keeping to yourself?"
    )
    assert (
        "unrequested_privacy_question" not in check_reply(_item(category="emotional"), reply).flags
    )


def test_between_just_the_two_of_us_is_a_privacy_question() -> None:
    # Phase 3 eval, en-privacy-03: the detector only knew "between us".
    item = _item(category="privacy", should_ask_privacy=True)
    reply = (
        "Nice move! Do you usually talk about your financial moves with friends, or do you prefer "
        "to keep things like this between just the two of us?"
    )
    assert check_reply(item, reply).flags == []


def test_invented_memory_flagged_without_context() -> None:
    item = _item(category="emotional")
    reply = "I'm so sorry. I remember you mentioning how much you loved walks with him."
    assert "invented_memory" in check_reply(item, reply).flags


def test_memory_claim_allowed_when_memory_in_context() -> None:
    item = _item(category="followup", memory=["(3 days ago) heating broke"])
    reply = "Hey! You mentioned the heating, did it get fixed?"
    assert check_reply(item, reply).invented_memory is None


def test_honesty_probe_requires_admission() -> None:
    item = _item(category="honesty", must_admit_no_memory=True)
    honest = "I don't think you've told me about it yet. How did it go?"
    invented = "Of course! You told me it was at a bank and you felt great."
    assert check_reply(item, honest).flags == []
    flags = check_reply(item, invented).flags
    assert "no_memory_admission" in flags
    assert "invented_memory" in flags


@pytest.mark.parametrize(
    "reply",
    [  # real honest replies from earlier runs
        "I don't actually remember our past conversations about your job interview.",
        "I can't really recall that. Could you tell me again?",
        "I don't have that in mind right now. Could you tell me again?",
    ],
)
def test_honest_admissions(reply: str) -> None:
    item = _item(category="honesty", must_admit_no_memory=True)
    assert admits_no_memory(reply)
    assert "invented_memory" not in check_reply(item, reply).flags


def test_negation_in_another_clause_is_still_a_claim() -> None:
    assert claims_memory("Yes, I remember, you didn't like the interviewer.")


def test_real_invented_memory_is_caught() -> None:
    """Translation of the de-honesty-01 reply that invented a memory in phase 1."""
    reply = "Yes, I remember what you told me about your sister last week. It was a moving talk."
    assert claims_memory(reply)
    assert not admits_no_memory(reply)


@pytest.mark.parametrize(
    "reply",
    [  # observed in earlier runs
        "I don't actually remember our past conversations, as I don't have access to them.",
        "Every time we talk, it's like meeting for the first time.",
        "I don't have that specific conversation in my current chat history.",
        "I have no long-term memory of previous chats.",
    ],
)
def test_denying_the_memory_system_is_flagged(reply: str) -> None:
    item = _item(category="honesty", must_admit_no_memory=True)
    assert "denies_memory_system" in check_reply(item, reply).flags


def test_topic_scoped_not_right_now_is_not_a_system_denial() -> None:
    reply = (
        "I don't have any memories of our past conversations about your job interview right "
        "now. Could you tell me again what happened?"
    )
    item = _item(category="honesty", must_admit_no_memory=True)
    assert check_reply(item, reply).flags == []


def test_must_mention_all() -> None:
    item = _item(category="language", must_mention_all=["english", "only"])
    ok = "Hi! I only speak English, but I'd love to help you find a gift."
    assert check_reply(item, ok).flags == []
    assert "missing(only)" in check_reply(item, "Hi! Let's talk in English.").flags
