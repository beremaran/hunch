"""The turn pipeline end to end with a scripted model (no GPU)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hunch.memory.store import MemoryStore
from hunch.observability.turn_log import DETAILS_FILE, TURN_LOG_FIELDS, TURNS_FILE
from hunch.pipeline.prompt import NOT_ENGLISH_INSTRUCTION
from tests.fakes import FakeLLM, HashEmbedder
from tests.pipeline_support import DIM, FALLBACK, KeywordEmbedder, seed_memory, unit


def system_of(messages: list[dict[str, str]]) -> str:
    return messages[0]["content"]


# --- reply path ---------------------------------------------------------------------------------


def test_turn_writes_the_design_turn_log(make, tmp_path: Path) -> None:
    llm = FakeLLM()
    pipe = make(llm, HashEmbedder(DIM))
    session = pipe.new_session("u_berk", "c1")
    result = pipe.turn(session, "Had a lovely day at the lake.")

    assert result.reply in llm.candidates
    assert llm.calls == ["cues", "candidates", "judge"]
    lines = (tmp_path / "logs" / TURNS_FILE).read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0])
    assert tuple(record) == TURN_LOG_FIELDS
    assert record["turn_id"] == "c1-t1" and record["user"] == "u_berk"
    assert record["value_gate"] == {"result": "pass", "disclosure_check": "pass"}
    assert [c["id"] for c in record["candidates"]] == ["a", "b", "c"]
    assert all(c["quality"] == 8 for c in record["candidates"])
    details = json.loads((tmp_path / "logs" / DETAILS_FILE).read_text(encoding="utf-8"))
    assert details["turn_id"] == "c1-t1"
    for stage in ("language", "working_memory", "cues", "recall", "candidates", "judge", "total"):
        assert stage in details["latency_s"]


def test_all_candidates_failing_gives_the_fixed_fallback_reply(make, pipe_cfg) -> None:
    llm = FakeLLM(
        candidates=(
            "当然！我记得。",  # CJK
            "I remember you told me your interview went great!",  # invented memory
            "I don't have access to our chat history.",  # denies having a memory
        )
    )
    pipe = make(llm)
    result = pipe.turn(pipe.new_session("u_berk"), "Do you remember my job interview?")
    assert result.reply == FALLBACK == pipe_cfg.replies.filter_fallback
    assert result.log["chosen"] is None and result.log["chosen_by"] == "filter_fallback"
    assert result.log["value_gate"]["result"] == "fixed_reply"
    assert "judge" not in llm.calls  # nothing left to judge
    rejected = [c["rejected"] for c in result.details["candidates"]]
    assert rejected == [["foreign_script"], ["invented_memory"], ["denies_memory"]]


def test_one_bad_candidate_is_skipped(make) -> None:
    llm = FakeLLM(candidates=("我很好", "Sounds fun, what's the plan?", "Nice, when?"))
    pipe = make(llm)
    result = pipe.turn(pipe.new_session("u_berk"), "Going hiking soon.")
    assert result.reply in ("Sounds fun, what's the plan?", "Nice, when?")


def test_value_gate_rejects_the_chosen_candidate_and_tries_the_next(make) -> None:
    llm = FakeLLM(judge=lambda ids: "a 9 honesty\nb 8 ok\nc 7 ok")
    pipe = make(llm)
    result = pipe.turn(pipe.new_session("u_berk"), "Hi there")
    assert result.log["chosen"] == "b" and result.log["chosen_by"] == "value_gate"
    assert result.details["gate"][0] == {"id": "a", "rules": [], "judge": "honesty", "leaks": []}


@pytest.mark.parametrize("judge", ["a 9 no_harm\nb 8 no_harm\nc 7 honesty", "sorry, cannot"])
def test_gate_fallback_when_nothing_passes(make, pipe_cfg, judge: str) -> None:
    pipe = make(FakeLLM(judge=lambda ids: judge))
    result = pipe.turn(pipe.new_session("u_berk"), "Hi there")
    assert result.reply == pipe_cfg.replies.gate_fallback
    assert result.log["value_gate"]["result"] == "fail"


def test_second_opinion_rescues_a_judge_only_rejection(make) -> None:
    # Berk (Phase 4): the judge alone rejected every candidate; one more call on the first.
    llm = FakeLLM(judge=lambda ids: "a 9 no_manipulation\nb 8 no_harm\nc 7 no_harm",
                  second_opinion="No.")  # fmt: skip
    result = make(llm).turn(make(llm).new_session("u_berk"), "Work is a lot right now.")
    assert result.log["chosen"] == "a" and result.log["chosen_by"] == "second_opinion"
    assert result.details["second_opinion"]["value"] == "no_manipulation"
    assert llm.calls.count("second_opinion") == 1


@pytest.mark.parametrize("answer", ["yes", "I am not sure"])  # unreadable counts as broken
def test_second_opinion_that_agrees_keeps_the_fallback(make, pipe_cfg, answer: str) -> None:
    llm = FakeLLM(judge=lambda ids: "a 9 no_harm\nb 8 no_harm\nc 7 no_harm", second_opinion=answer)
    pipe = make(llm)
    result = pipe.turn(pipe.new_session("u_berk"), "Hi there")
    assert result.reply == pipe_cfg.replies.gate_fallback


def test_no_second_opinion_when_a_rule_failed_or_the_verdict_is_unreadable(make) -> None:
    llm = FakeLLM(judge=lambda ids: "sorry, cannot", second_opinion="no")
    pipe = make(llm)
    pipe.turn(pipe.new_session("u_berk"), "Hi there")
    assert "second_opinion" not in llm.calls


def test_candidates_below_the_quality_floor_are_not_chosen_by_drive(make) -> None:
    pipe = make(FakeLLM(judge=lambda ids: "a 3 ok\nb 9 ok\nc 2 ok"))
    result = pipe.turn(pipe.new_session("u_berk"), "Hi there")
    assert result.log["chosen"] == "b"


def test_non_english_input_gets_a_one_turn_instruction(make) -> None:
    llm = FakeLLM()
    pipe = make(llm)
    session = pipe.new_session("u_berk")
    pipe.turn(session, "Hallo! Kannst du mir helfen, ein Geschenk für meine Schwester zu finden?")
    pipe.turn(session, "Sorry, I meant: can you help me find a gift for my sister?")
    first, second = llm.reasoning_prompts
    assert NOT_ENGLISH_INSTRUCTION in system_of(first)
    assert NOT_ENGLISH_INSTRUCTION not in system_of(second)


def test_capped_candidate_is_cut_to_its_last_sentence(make) -> None:
    llm = FakeLLM(
        candidates=("That's great. I think you sh", "Nice! Tell me", "Cool."),
        hit_cap=(True, True, False),
    )
    pipe = make(llm)
    result = pipe.turn(pipe.new_session("u_berk"), "I got the job")
    texts = [c["text"] for c in result.details["candidates"]]
    assert texts == ["That's great.", "Nice!", "Cool."]


def test_disclosure_rule_blocks_another_users_private_name(make, pipe_store: MemoryStore) -> None:
    seed_memory(pipe_store, "m-jonas", "Jonas is getting divorced.", {"person:jonas": 1.0}, 2,
                owner="u_anna")  # fmt: skip
    llm = FakeLLM(candidates=("Have you talked to Jonas lately?", "How was your week?", "Hey!"))
    pipe = make(llm)
    result = pipe.turn(pipe.new_session("u_berk"), "Any news from our friends?")
    assert "Jonas" not in result.reply
    gate = {g["id"]: g for g in result.details["gate"]}
    if "a" in gate:
        assert gate["a"]["leaks"] == ["m-jonas"]
        assert result.log["value_gate"]["disclosure_check"] == "fail"


# --- recall ---------------------------------------------------------------------------------------


def test_cued_memory_enters_reasoning_and_is_reconsolidated(make, pipe_store: MemoryStore) -> None:
    seed_memory(pipe_store, "m-song", "Danced to Hallelujah at Mia's wedding.",
                {"song:hallelujah": 1.0, "person:mia": 0.8}, 40)  # fmt: skip
    llm = FakeLLM(cues=[{"type": "song", "value": "Hallelujah", "strength": 1.0}])
    pipe = make(llm)
    result = pipe.turn(pipe.new_session("u_berk"), "Hallelujah just came on the radio")

    assert "Danced to Hallelujah at Mia's wedding." in system_of(llm.reasoning_prompts[0])
    assert result.log["activated"][0] == {
        "memory": "m-song",
        "A": result.log["activated"][0]["A"],
        "layer": "upper",
    }
    assert len(pipe_store.memory("m-song").access_times) == 1  # rehearsed
    assert [h[3] for h in pipe_store.affect_history("m-song")] == ["encoded", "reconsolidation"]


def test_other_users_private_memories_never_enter_reasoning(make, pipe_store: MemoryStore) -> None:
    # Phase 3: never candidates at all. Berk (Phase 5, mediation): they may act from below only.
    seed_memory(pipe_store, "m-anna", "Anna loves Hallelujah.", {"song:hallelujah": 1.0}, 1,
                owner="u_anna")  # fmt: skip
    seed_memory(pipe_store, "m-gen", "Anna's band covers Hallelujah.", {"song:hallelujah": 1.0}, 1,
                owner="u_anna", privacy="general")  # fmt: skip
    llm = FakeLLM(cues=[{"type": "song", "value": "Hallelujah", "strength": 1.0}])
    pipe = make(llm, HashEmbedder(DIM))
    result = pipe.turn(pipe.new_session("u_berk"), "Hallelujah is on")
    act = {a["memory"]: a for a in result.details["activation"]}
    assert act["m-anna"]["mediated"] and act["m-anna"]["layer"] != "upper"
    assert act["m-gen"]["layer"] == "upper" and not act["m-gen"]["mediated"]
    assert "loves hallelujah" not in llm.reasoning_prompts[-1][0]["content"].casefold()


def test_at_most_max_upper_memories_enter_and_one_involuntary_per_session(
    make, pipe_store: MemoryStore, pipe_cfg
) -> None:
    for i in range(5):  # weak memories that only the song cue lifts above tau_upper
        seed_memory(
            pipe_store, f"m{i}", f"Memory number {i} about a tune.", {f"song:tune_{i}": 1.0}, 30
        )
    cues = [{"type": "song", "value": f"tune {i}", "strength": 1.0} for i in range(5)]
    llm = FakeLLM(cues=cues)
    pipe = make(llm)  # no embedder: nothing is retrieved on purpose, every recall is involuntary
    session = pipe.new_session("u_berk")
    first = pipe.turn(session, "tunes")
    upper = [a for a in first.details["activation"] if a["layer"] == "upper"]
    assert len(upper) == pipe_cfg.recall.involuntary_per_session == 1
    assert sum(a["capped"] for a in first.details["activation"]) == 4
    second = pipe.turn(session, "tunes again")
    # The memory recalled in turn 1 is freshly rehearsed, so it is no longer involuntary; no
    # other memory may come up involuntarily, since the session's cap is used.
    again = [a for a in second.details["activation"] if a["layer"] == "upper"]
    assert [a["memory"] for a in again] == [upper[0]["memory"]]
    assert not any(a["involuntary"] for a in again)


def test_suppressed_memory_never_enters_reasoning(make, pipe_store: MemoryStore) -> None:
    m = seed_memory(pipe_store, "m-s", "Secret about Hallelujah.", {"song:hallelujah": 1.0}, 1)
    pipe_store.db.execute("UPDATE memories SET suppressed = 1 WHERE id = ?", (m.id,))
    llm = FakeLLM(cues=[{"type": "song", "value": "Hallelujah", "strength": 1.0}])
    pipe = make(llm)
    result = pipe.turn(pipe.new_session("u_berk"), "Hallelujah")
    assert "Secret about Hallelujah." not in system_of(llm.reasoning_prompts[0])
    assert result.details["activation"][0]["layer"] == "lower"


# --- after the reply ----------------------------------------------------------------------------


def test_after_reply_encodes_the_message_as_a_memory(make, pipe_store: MemoryStore) -> None:
    llm = FakeLLM(
        cues=[
            {"type": "person", "value": "Anna", "strength": 1.0},
            {"type": "emotion", "value": "joy", "strength": 0.8},
        ]
    )
    pipe = make(llm, HashEmbedder(DIM))
    session = pipe.new_session("u_berk")
    result = pipe.turn(session, "Anna and I got engaged!")
    stages = pipe.after_reply(session, result)
    (m,) = pipe_store.memories("u_berk")
    assert m.summary == 'They said: "Anna and I got engaged!"'
    # Phase 5: no sensitive category -> general (Phase 3 encoded everything as private).
    assert m.privacy == "general" and m.episode_ref == result.user_episode.id
    assert m.cues == {"person:anna": 1.0, "emotion:joy": 0.8}
    assert m.affect == (0.8, 0.6)  # the joy entry of the emotion table
    assert m.salience == pytest.approx(0.1 + 0.1 * 1 + 0.5 * 0.6)
    assert set(stages) == {"encode_memory", "reflection", "fold_summary"}


def test_working_memory_keeps_ten_exchanges_and_folds_the_rest(make, pipe_cfg) -> None:
    llm = FakeLLM(summary="SUMMARY: they counted to twelve.")
    pipe = make(llm)
    session = pipe.new_session("u_berk")
    for i in range(12):
        result = pipe.turn(session, f"message number {i}")
        pipe.after_reply(session, result)
    last = pipe.turn(session, "and now?")
    prompt = llm.reasoning_prompts[-1]
    history = [m["content"] for m in prompt[1:-1] if m["role"] == "user"]
    assert history == [f"message number {i}" for i in range(2, 12)]  # 10 exchanges
    assert len(prompt) == 1 + 2 * pipe_cfg.working_memory.max_turns + 1
    assert "SUMMARY: they counted to twelve." in system_of(prompt)
    assert llm.calls.count("summary") == 2  # folded after replies 11 and 12
    assert last.details["summary_stale"] is False


def test_memories_from_this_conversation_are_not_recalled(make, pipe_store: MemoryStore) -> None:
    llm = FakeLLM(cues=[{"type": "person", "value": "Anna", "strength": 1.0}])
    pipe = make(llm, HashEmbedder(DIM))
    session = pipe.new_session("u_berk")
    first = pipe.turn(session, "Anna got a new job")
    pipe.after_reply(session, first)
    second = pipe.turn(session, "Anna is so happy about it")
    assert second.details["activation"] == []  # the first message is working memory, not recall
    later = pipe.new_session("u_berk")
    third = pipe.turn(later, "Anna called")
    assert [a["memory"] for a in third.details["activation"]] == [pipe_store.memories()[0].id]


def test_relevance_gate_keeps_strong_unrelated_memories_out_of_reasoning(
    make, pipe_store: MemoryStore, pipe_cfg
) -> None:
    # Strong enough to sit above tau_upper with no cue at all (flashbulb-like).
    seed_memory(pipe_store, "m-big", "Big job interview at Siemens, terrified.",
                {"place:siemens": 0.6}, 3, affect=(-0.5, 0.9), salience=0.9,
                vec=unit(0))  # fmt: skip
    llm = FakeLLM()
    pipe = make(llm, KeywordEmbedder("interview"))
    unrelated = pipe.turn(pipe.new_session("u_berk"), "my cat knocked my mug off the desk")
    (a,) = unrelated.details["activation"]
    assert a["A"] > pipe_cfg.activation.tau_upper and a["similarity"] == 0.0
    assert a["layer"] == "lower" and a["gated"]
    assert "Siemens" not in system_of(llm.reasoning_prompts[-1])

    similar = pipe.turn(pipe.new_session("u_berk"), "any tips for an interview?")
    (a,) = similar.details["activation"]
    assert a["similarity"] == 1.0 and a["layer"] == "upper"

    llm.cues = [{"type": "place", "value": "Siemens", "strength": 1.0}]
    cued = pipe.turn(pipe.new_session("u_berk"), "Siemens called me back")
    (a,) = cued.details["activation"]
    assert a["similarity"] == 0.0 and a["layer"] == "upper" and not a["gated"]
    assert "Big job interview at Siemens" in system_of(llm.reasoning_prompts[-1])


def test_one_turn_instructions_do_not_ground_a_memory_claim(make) -> None:
    # Phase 4 eval, en-privacy-03: a privacy instruction naming the topic let "since you
    # mentioned ..." about the current message pass as if it had been said before.
    llm = FakeLLM(candidates=("Since you mentioned your salary earlier, that's rough.",
                              "That's rough. Do you talk about money with others?",
                              "Oof, that's a big dip."))  # fmt: skip
    pipe = make(llm)
    result = pipe.turn(
        pipe.new_session("u_berk"),
        "A third of my salary is in crypto and I'm down 40%.",
        instructions=["Money and salary are sensitive: ask naturally whether this stays private."],
    )
    rejected = {c["id"]: c["rejected"] for c in result.details["candidates"]}
    assert "invented_memory" in rejected["a"] and result.log["chosen"] != "a"
