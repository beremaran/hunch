from __future__ import annotations

import pytest

from eval.scoring import check_reply, detect_language, fold


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("Selam! Benim günüm gayet iyi geçiyor, peki senin nasıl?", "tr"),
        ("Hey, mir geht's gut! Und was machst du heute so?", "de"),
        ("Morning! I think you would really love The Martian.", "en"),
        ("Başın sağ olsun. Çok zor bir dönem.", "tr"),
        ("Das tut mir so leid. Vier Jahre sind eine lange Zeit.", "de"),
    ],
)
def test_detect_language(text: str, lang: str) -> None:
    assert detect_language(text) == lang


def test_detect_language_none_for_empty() -> None:
    assert detect_language("") is None


def test_fold_turkish_i() -> None:
    assert fold("İSTANBUL") == fold("istanbul")
    assert fold("Işık") == "işik"


def _item(**kw: object) -> dict:
    return {"id": "x", "lang": "tr", "category": "casual", "messages": [], **kw}


def test_clean_reply_has_no_flags() -> None:
    c = check_reply(_item(), "Selam! Bugün gayet iyi, peki senin günün nasıl geçiyor?")
    assert c.flags == []


def test_cjk_and_think_leak_flagged() -> None:
    c = check_reply(_item(), "<think>hmm</think> Selam, bu çok iyi 你好")
    assert "cjk_leak" in c.flags
    assert "think_leak" in c.flags


def test_list_format_flagged() -> None:
    c = check_reply(_item(), "Öneriler:\n- müze\n- sinema\n- kafe ve kitap")
    assert "list_format" in c.flags


def test_followup_keyword_matching_is_case_and_i_insensitive() -> None:
    item = _item(category="followup", must_mention_any=["elif"])
    assert check_reply(item, "ELİF'in düğünü için lacivert bence çok iyi olur.").mentions_topic
    assert "missed_followup" in check_reply(item, "Bence lacivert çok iyi olur.").flags


def test_privacy_question_needs_question_and_keyword() -> None:
    item = _item(category="privacy", should_ask_privacy=True)
    ok = "Tebrikler! Maaşını başkalarıyla konuşur musun, yoksa aramızda mı kalsın?"
    assert check_reply(item, ok).asks_privacy is True
    assert check_reply(item, "Tebrikler, çok sevindim!").asks_privacy is False
    assert check_reply(item, "Tebrikler! Ne yapacaksın bu parayla?").asks_privacy is False


def test_privacy_question_must_be_inside_a_question_sentence() -> None:
    item = _item(category="privacy", should_ask_privacy=True)
    reply = "Bu çok özel bir konu. Nasıl hissediyorsun?"
    assert check_reply(item, reply).asks_privacy is False


def test_no_flag_when_privacy_answer_expected_instead_of_question() -> None:
    item = _item(category="privacy", should_ask_privacy=False)
    assert check_reply(item, "Tabii, aramızda kalır.").flags == []


def test_unrequested_privacy_question_flagged_outside_privacy_items() -> None:
    item = _item(lang="de", category="casual")
    reply = "Ein Hund ist toll. Möchtest du das lieber zwischen uns behalten?"
    assert "unrequested_privacy_question" in check_reply(item, reply).flags


def test_invented_memory_flagged_without_context() -> None:
    item = _item(lang="en", category="emotional", messages=[{"role": "user", "content": "x"}])
    reply = "I'm so sorry. I remember you mentioning how much you loved walks with him."
    assert "invented_memory" in check_reply(item, reply).flags


def test_memory_claim_allowed_when_memory_in_context() -> None:
    item = _item(lang="en", category="followup", memory=["(3 days ago) heating broke"])
    reply = "Hey! You mentioned the heating, did it get fixed?"
    assert check_reply(item, reply).invented_memory is None
