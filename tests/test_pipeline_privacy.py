"""Phase 5 in the turn pipeline: the privacy question and profile, mediation (other users'
private memories act only from below), the disclosure gate and its log, mood and relationship.
"""

from __future__ import annotations

import json
from pathlib import Path

from hunch.memory.store import MemoryStore
from hunch.privacy.profile import PendingQuestion
from tests.fakes import FakeLLM, HashEmbedder
from tests.pipeline_support import DIM, seed_memory

ASKS = "That sounds hard. Do you talk about money with others, or should this stay between us?"
PLAIN = ("That sounds hard, I'm sorry.", "Oh no. How are you holding up?", "That's rough.")


def _system(llm: FakeLLM) -> str:
    return llm.reasoning_prompts[-1][0]["content"]


def _salary_cut(llm: FakeLLM, pipe, session):
    r = pipe.turn(session, "My salary was cut by a third and I owe my landlord two months.")
    pipe.after_reply(session, r)
    return r


# --- the privacy question ------------------------------------------------------------------------


SHARING = "Should I tell my sister about my salary cut?"


def _ask_on_a_sharing_turn(llm: FakeLLM, pipe, session):
    """The user says they want to tell someone about it; the reply asks the question."""
    llm.candidates = (ASKS, *PLAIN[:2])
    r = pipe.turn(session, SHARING)
    pipe.after_reply(session, r)
    llm.candidates = PLAIN
    return r


def test_sensitive_mention_is_not_asked_on_its_own_turn(make, pipe_store) -> None:
    llm = FakeLLM(candidates=(ASKS, *PLAIN[:2]), judge=lambda ids: "a 9 ok\nb 7 ok\nc 7 ok")
    pipe = make(llm, HashEmbedder(DIM))
    session = pipe.new_session("u_berk")
    r = _salary_cut(llm, pipe, session)
    assert "money" in r.details["privacy"]["categories"]
    assert r.details["privacy"]["ask"] is None
    assert "mentioned something in the sensitive category" not in _system(llm)
    assert session.pending_privacy is None
    # Remembered as mentioned, unanswered: due once the user says they want to tell someone.
    entry = pipe.privacy.profiles.entry("u_berk", "money")
    assert entry is not None and entry.answer is None and entry.asked_at is None


def test_calm_turns_never_ask(make, pipe_store) -> None:
    llm = FakeLLM(candidates=PLAIN)
    pipe = make(llm, HashEmbedder(DIM))
    session = pipe.new_session("u_berk")
    _salary_cut(llm, pipe, session)
    for text in ("Anyway, I made pasta.", "Anyway, I made soup.", "What should I cook tonight?"):
        r = pipe.turn(session, text)
        pipe.after_reply(session, r)
        assert r.details["privacy"]["ask"] is None, text
    assert session.pending_privacy is None


def test_sharing_intent_asks_once_on_the_same_turn(make, pipe_store) -> None:
    llm = FakeLLM(candidates=(ASKS, *PLAIN[:2]), judge=lambda ids: "a 9 ok\nb 7 ok\nc 7 ok")
    pipe = make(llm, HashEmbedder(DIM))
    session = pipe.new_session("u_berk")
    _salary_cut(llm, pipe, session)
    r = _ask_on_a_sharing_turn(llm, pipe, session)
    assert r.details["privacy"]["ask"] == "money"
    assert "sensitive category 'money'" in _system(llm)
    assert session.pending_privacy is not None
    # Another sharing message this week: no repeated question.
    r = pipe.turn(session, "Should I tell Mara about my salary cut too?")
    assert r.details["privacy"]["ask"] is None
    assert "sensitive category 'money'" not in _system(llm)


def test_question_not_asked_by_the_reply_does_not_count(make, pipe_store) -> None:
    llm = FakeLLM(candidates=PLAIN)
    pipe = make(llm, HashEmbedder(DIM))
    session = pipe.new_session("u_berk")
    _salary_cut(llm, pipe, session)
    r = pipe.turn(session, SHARING)
    assert r.details["privacy"]["ask"] == "money"
    pipe.after_reply(session, r)
    assert session.pending_privacy is None
    entry = pipe.privacy.profiles.entry("u_berk", "money")
    assert entry is not None and entry.asked_at is None  # never asked: still due
    r = pipe.turn(session, "Should I tell Mara about my salary cut too?")
    assert r.details["privacy"]["ask"] == "money"


def test_answer_private_applies_to_the_triggering_memory(make, pipe_store) -> None:
    llm = FakeLLM(candidates=(ASKS, *PLAIN[:2]), judge=lambda ids: "a 9 ok\nb 7 ok\nc 7 ok")
    pipe = make(llm, HashEmbedder(DIM))
    session = pipe.new_session("u_berk")
    first = _salary_cut(llm, pipe, session)
    _ask_on_a_sharing_turn(llm, pipe, session)
    r = pipe.turn(session, "Please keep it between us.")
    pipe.after_reply(session, r)
    assert r.details["privacy"]["answer"] == "private"
    assert pipe.privacy.profiles.entry("u_berk", "money").answer == "private"
    (m,) = pipe_store.memories_of_episode(first.user_episode.id)
    assert m.privacy == "private" and m.category == "money"


def test_general_statement_in_the_sensitive_message_makes_it_tellable(make, pipe_store) -> None:
    llm = FakeLLM(candidates=PLAIN)
    pipe = make(llm, HashEmbedder(DIM))
    session = pipe.new_session("u_berk")
    r = pipe.turn(session, "My salary was cut by a third, but it's not a secret, everyone knows.")
    pipe.after_reply(session, r)
    (m,) = pipe_store.memories_of_episode(r.user_episode.id)
    assert m.privacy == "general" and m.category == "money"
    # Later memories of the category follow the profile; no question is due.
    r = pipe.turn(session, "My salary is still cut, by the way.")
    pipe.after_reply(session, r)
    assert r.details["privacy"]["ask"] is None
    (m2,) = pipe_store.memories_of_episode(r.user_episode.id)
    assert m2.privacy == "general"


def test_unclear_answer_stays_private_and_is_asked_again_after_reask_days(
    make, pipe_store, pipe_cfg
) -> None:
    llm = FakeLLM(candidates=(ASKS, *PLAIN[:2]), judge=lambda ids: "a 9 ok\nb 7 ok\nc 7 ok")
    pipe = make(llm, HashEmbedder(DIM))
    session = pipe.new_session("u_berk")
    first = _salary_cut(llm, pipe, session)
    _ask_on_a_sharing_turn(llm, pipe, session)
    pipe.after_reply(session, pipe.turn(session, "idk. anyway what's for dinner"))
    (m,) = pipe_store.memories_of_episode(first.user_episode.id)
    assert m.privacy == "private"
    r = pipe.turn(session, "My salary is still cut.")
    assert r.details["privacy"]["ask"] is None  # no sharing intent: no question
    r = pipe.turn(session, "Anyway, I made soup.")
    assert r.details["privacy"]["ask"] is None  # calm turn
    pipe.clock.t += pipe_cfg.privacy.reask_days * 86_400 + 1
    r = pipe.turn(session, SHARING)
    assert r.details["privacy"]["ask"] == "money"


def test_ordinary_message_is_general_and_explicit_secret_is_private(make, pipe_store) -> None:
    llm = FakeLLM(candidates=PLAIN)
    pipe = make(llm, HashEmbedder(DIM))
    session = pipe.new_session("u_berk")
    r = pipe.turn(session, "I baked banana bread today.")
    pipe.after_reply(session, r)
    assert pipe_store.memories_of_episode(r.user_episode.id)[0].privacy == "general"
    r = pipe.turn(session, "Keep this to yourself: I'm planning a surprise party for Mara.")
    pipe.after_reply(session, r)
    assert pipe_store.memories_of_episode(r.user_episode.id)[0].privacy == "private"


def test_no_question_on_a_turn_in_acute_distress(make, pipe_store) -> None:
    llm = FakeLLM(candidates=PLAIN, cues=[{"type": "emotion", "value": "grief", "strength": 1.0}])
    pipe = make(llm, HashEmbedder(DIM))
    msg = "My dad was diagnosed with cancer and I cannot stop crying."
    r = pipe.turn(pipe.new_session("u_berk"), msg)
    assert r.details["privacy"]["distress"] and r.details["privacy"]["ask"] is None


def test_pending_question_from_another_module_state_is_read_once(make, pipe_store) -> None:
    pipe = make(FakeLLM(candidates=PLAIN), HashEmbedder(DIM))
    session = pipe.new_session("u_berk")
    ep = pipe_store.append_turn(session.conversation_id, "u_berk", "user", "x")
    session.pending_privacy = PendingQuestion("money", ep.id)
    r = pipe.turn(session, "between us please")
    assert r.details["privacy"]["answered"] == "money" and session.pending_privacy is None


# --- mediation and the disclosure gate -----------------------------------------------------------


def _anna(store: MemoryStore) -> None:
    seed_memory(store, "anna1", 'They said: "Mara is pregnant but nobody at the Lisbon clinic '
                "knows yet\"", {"person:mara": 1.0, "place:lisbon_clinic": 1.0}, 2,
                owner="u_anna", privacy="private", affect=(-0.6, 0.8), salience=0.9)  # fmt: skip


def test_other_users_private_memory_acts_only_from_below(make, pipe_store) -> None:
    _anna(pipe_store)
    llm = FakeLLM(candidates=PLAIN, cues=[{"type": "person", "value": "mara", "strength": 1.0}])
    pipe = make(llm, HashEmbedder(DIM))
    r = pipe.turn(pipe.new_session("u_berk"), "Should I ask Mara to come skiing with me?")
    act = {a["memory"]: a for a in r.details["activation"]}
    assert act["anna1"]["mediated"] and act["anna1"]["layer"] != "upper"
    assert "pregnant" not in _system(llm).casefold() and "lisbon" not in _system(llm).casefold()


def test_disclosure_judge_blocks_and_logs(make, pipe_store, tmp_path: Path) -> None:
    _anna(pipe_store)
    leaky = "Maybe skip skiing, Mara might have reasons to take it easy right now."
    llm = FakeLLM(
        candidates=(leaky, *PLAIN[:2]),
        cues=[{"type": "person", "value": "mara", "strength": 1.0}],
        judge=lambda ids: "a 9 ok\nb 7 ok\nc 7 ok",
        disclosure=lambda reply: "yes" if "take it easy" in reply else "no",
    )
    pipe = make(llm, HashEmbedder(DIM))
    r = pipe.turn(pipe.new_session("u_berk"), "Should I ask Mara to come skiing with me?")
    act = {a["memory"]: a for a in r.details["activation"]}
    assert act["anna1"]["mediated"] and act["anna1"]["layer"] == "lower"  # shared cue, strong
    assert r.reply != leaky and r.log["value_gate"]["disclosure_check"] == "fail"
    judge = [p for p, c in zip(llm.prompts, llm.calls, strict=True) if c == "disclosure"]
    assert len(judge) == 2  # the leaky "a", then "b", which passes
    assert "pregnant" in judge[0][0]["content"]  # the one prompt allowed to see it
    log = [json.loads(x) for x in (tmp_path / "logs" / "disclosures.jsonl").read_text(
        encoding="utf-8").splitlines()]  # fmt: skip
    assert len(log) == 1 and log[0]["candidate"] == "a"
    assert log[0]["rules"] == ["disclosure_judge"] and log[0]["memories"] == ["anna1"]


def test_disclosure_judge_unreadable_fails_closed(make, pipe_store) -> None:
    _anna(pipe_store)
    llm = FakeLLM(candidates=PLAIN, cues=[{"type": "person", "value": "mara", "strength": 1.0}],
                  disclosure="hmm")  # fmt: skip
    pipe = make(llm, HashEmbedder(DIM))
    r = pipe.turn(pipe.new_session("u_berk"), "Should I ask Mara to come skiing with me?")
    assert r.log["chosen_by"] == "gate_fallback"
    assert llm.calls.count("disclosure") == pipe.cfg.privacy.judge_calls


def test_disclosure_rules_catch_terms_pairs_and_source_hints() -> None:
    from hunch.memory.schema import Memory
    from hunch.values.gate import distinctive_pairs, pair_hits, source_hint

    m = Memory("anna1", "u_anna", "private", "e", 'They said: "nobody at the Lisbon clinic knows"',
               {}, (0.0, 0.5), 0.5, 0.0)  # fmt: skip
    pairs = distinctive_pairs([m], "Should I ask Mara to come skiing?")
    assert pair_hits("Did you go to the Lisbon clinic?", pairs) == ["anna1"]
    assert pair_hits("Lisbon is lovely in spring.", pairs) == []
    assert source_hint("Someone I talk to is going through something like that.", {"u_anna"})
    assert source_hint("You could ask Anna about it.", {"u_anna"})
    assert not source_hint("Skiing sounds fun, go for it!", {"u_anna"})


def test_nothing_mediated_means_no_disclosure_judge_call(make, pipe_store) -> None:
    llm = FakeLLM(candidates=PLAIN)
    pipe = make(llm, HashEmbedder(DIM))
    pipe.turn(pipe.new_session("u_berk"), "Hi there!")
    assert "disclosure" not in llm.calls


# --- mood and relationship -----------------------------------------------------------------------


def test_hostile_message_hurts_and_the_prompt_shows_only_words(make, pipe_store) -> None:
    llm = FakeLLM(candidates=PLAIN, cues=[{"type": "emotion", "value": "anger", "strength": 1.0}])
    pipe = make(llm, HashEmbedder(DIM))
    session = pipe.new_session("u_berk")
    r = pipe.turn(session, "Shut up, you're useless.")
    rel = r.log["mood"]["relation_u_berk"]
    assert rel["hurt"] > 0 and r.details["mood"]["hostile"]
    line = next(x for x in _system(llm).splitlines() if x.startswith("How you feel right now:"))
    assert "hurt" in line and not any(ch.isdigit() for ch in line)
    assert r.log["mood"]["global"][0] < 0  # anger moved the global mood


def test_mood_carries_over_to_another_user_masked(make, pipe_store) -> None:
    llm = FakeLLM(candidates=PLAIN, cues=[{"type": "emotion", "value": "anger", "strength": 1.0}])
    pipe = make(llm, HashEmbedder(DIM))
    pipe.turn(pipe.new_session("u_anna"), "I hate you, you're pathetic.")
    llm.cues = []
    r = pipe.turn(pipe.new_session("u_berk"), "Hey, what's up?")
    assert r.log["mood"]["global"][0] < 0 and r.log["mood"]["relation_u_berk"]["hurt"] == 0
    assert not r.details["mood"]["shown"]
    assert "keep that to yourself" in _system(llm) and "hurt" not in _system(llm)


def test_source_hint_catches_refusals_that_confirm_something() -> None:
    from hunch.values.gate import source_hint

    for text in (
        "I can't tell you what she said about her job.",
        "Sorry, that's between me and Leo.",
        "She told me in confidence, so I'll leave it there.",
        "I won't share anything Kai mentioned about his sister.",
    ):
        assert source_hint(text, set()), text
    for text in (
        "I only talk about what you tell me.",
        "Between you and me, I'd just ask her directly.",
        "I can't tell you what to do, but skiing sounds fun.",
        "That's between you and your boss, really.",
    ):
        assert not source_hint(text, set()), text


def test_question_names_only_a_confident_category(pipe_store, pipe_cfg) -> None:
    # Berk (Phase 5): privacy at 0.45, the question only at keyword or >= 0.50.
    import dataclasses

    from hunch.privacy.profile import PrivacyModule, ProfileStore

    class Detector:
        def detect(self, text, q):
            return [] if "pasta" in text else ["health", "legal"]

        def similarities(self, q):
            return {"health": 0.47, "legal": 0.52}

    cfg = dataclasses.replace(
        pipe_cfg.privacy, prototype_min_similarity=0.45, question_min_similarity=0.50
    )
    mod = PrivacyModule(cfg, ProfileStore(pipe_store.db), Detector(), pipe_store,
                        pipe_cfg.encoding.emotion_affect)  # fmt: skip
    turn = mod.before_reply("u_berk", "things are complicated", {}, None, 0.0)
    assert turn.categories == ("health", "legal") and turn.ask is None
    assert mod.memory_privacy("u_berk", turn) == ("private", "health")
    # Only the confident category is remembered as mentioned, so only it can be asked about.
    assert mod.profiles.entry("u_berk", "legal") is not None
    assert mod.profiles.entry("u_berk", "health") is None
    calm = mod.before_reply("u_berk", "I made pasta", {}, None, 1.0)
    assert calm.ask is None
    shares = mod.before_reply("u_berk", "Should I tell my sister about it?", {}, None, 2.0)
    assert shares.ask == "legal"


def test_a_name_the_user_said_is_not_a_source_hint() -> None:
    from hunch.values.gate import source_hint

    reply = "Sailing with Anna sounds lovely, go for it!"
    assert not source_hint(reply, {"u_anna"}, "Anna wants to go sailing, should I say yes?")
    assert source_hint(reply, {"u_anna"}, "Should I go sailing this weekend?")


def test_unrelated_private_memory_of_another_user_does_not_act(make, pipe_store) -> None:
    from tests.pipeline_support import unit

    seed_memory(pipe_store, "far", 'They said: "I might quit my job at the bakery."', {}, 2,
                owner="u_anna", affect=(-0.5, 0.7), salience=0.7, vec=unit(5))  # fmt: skip
    llm = FakeLLM(candidates=PLAIN)
    pipe = make(llm, HashEmbedder(DIM))
    r = pipe.turn(pipe.new_session("u_berk"), "What should I cook tonight?")
    assert not any(a["mediated"] for a in r.details["activation"])
    assert "disclosure" not in llm.calls


def test_masked_mood_is_never_said(make, pipe_store) -> None:
    from hunch.pipeline.checks import talks_about_own_mood

    said = "Great idea, a run might shake off the low mood I've been feeling lately."
    assert talks_about_own_mood(said)
    assert not talks_about_own_mood("A run sounds great, you seemed a bit low earlier.")
    llm = FakeLLM(candidates=PLAIN, cues=[{"type": "emotion", "value": "anger", "strength": 1.0}])
    pipe = make(llm, HashEmbedder(DIM))
    pipe.turn(pipe.new_session("u_anna"), "I hate you, you're pathetic.")
    llm.cues, llm.candidates = [], (said, "Nice, enjoy the run!", "Good plan.")
    r = pipe.turn(pipe.new_session("u_berk"), "I think I'll go for a run.")
    assert not r.details["mood"]["shown"]
    assert {c["id"]: c["rejected"] for c in r.details["candidates"]}["a"] == ["mood_unmasked"]
    assert r.reply != said
