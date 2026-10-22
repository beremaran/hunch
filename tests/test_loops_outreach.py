"""What Hunch writes first (Phase 6): kind choice, instructions, and the outreach pipeline path."""

from __future__ import annotations

import random

import pytest

from hunch.loops.outreach import (
    FALLBACK,
    choose_kind,
    describes_own_experience,
    instruction_for,
)
from hunch.loops.store import OpenLoop
from hunch.pipeline.turn import OUTREACH_TRIGGER
from tests.fakes import FakeLLM, HashEmbedder
from tests.pipeline_support import DIM

LOOP = OpenLoop("loop-1", "u_berk", "job interview", "my interview is on Thursday at 2pm",
                "How did the interview go?", "general", 0.0, 0.0)  # fmt: skip


def test_a_due_loop_comes_first() -> None:
    assert choose_kind(LOOP, None, random.Random(1)) == "memory"


def test_starters_never_repeat_the_last_kind() -> None:
    rng = random.Random(7)
    last = "fun"
    for _ in range(50):
        kind = choose_kind(None, last, rng)
        assert kind != last
        last = kind


def test_memory_instruction_carries_the_users_words_and_the_question() -> None:
    text = instruction_for("memory", LOOP)
    assert "my interview is on Thursday at 2pm" in text
    assert "How did the interview go?" in text


def test_starter_instruction_does_not_refer_to_the_past() -> None:
    for kind in ("small_talk", "fun", "curious"):
        text = instruction_for(kind, None)
        assert "Do not refer to anything the user said before" in text


def test_outreach_follow_up_passes_when_it_uses_the_loop_words(make) -> None:
    llm = FakeLLM(candidates=(
        "Hey, how did the interview go on Thursday?",
        "Hi there, how did the interview go?",
        "Hello, how did it go?",
    ))  # fmt: skip
    pipe = make(llm, HashEmbedder(DIM))
    out = pipe.outreach(pipe.new_session("u_berk"), "memory", LOOP)
    assert out.chosen and "interview" in out.reply
    assert llm.reasoning_prompts[-1][-1]["content"] == OUTREACH_TRIGGER  # not stored


def test_invented_memory_in_a_starter_falls_back(make) -> None:
    llm = FakeLLM(candidates=(
        "You told me last week you love sailing, how was it?",
        "You mentioned your sister again, how is she?",
        "Last time you said you were tired, still?",
    ))  # fmt: skip
    pipe = make(llm, HashEmbedder(DIM))
    out = pipe.outreach(pipe.new_session("u_berk"), "small_talk", None)
    assert out.chosen is False and out.reply == FALLBACK


def test_outreach_is_stored_so_the_next_reply_sees_it(make, pipe_store) -> None:
    llm = FakeLLM(candidates=("Quick one: what are you up to this weekend?",) * 3)
    pipe = make(llm, HashEmbedder(DIM))
    session = pipe.new_session("u_berk")
    out = pipe.outreach(session, "small_talk", None)
    stored = pipe_store.turns(session.conversation_id)
    assert [(t.role, t.text) for t in stored][-1] == ("assistant", out.reply)


@pytest.mark.parametrize(
    "text",
    [
        "I was just reading about octopuses.",
        "I've been thinking about the ocean lately.",
        "I just realized that octopuses have three hearts.",
    ],
)
def test_made_up_experiences_are_caught(text: str) -> None:
    assert describes_own_experience(text)


@pytest.mark.parametrize(
    "text",
    [
        "How did the interview go?",
        "Would you rather fly or turn invisible?",
        "What are you reading lately?",
    ],
)
def test_questions_about_the_user_are_not_experiences(text: str) -> None:
    assert not describes_own_experience(text)
