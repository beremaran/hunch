"""Phase 4 in the turn pipeline: when a Hunch forms, when its flag reaches a prompt, the asked-why
and think-more triggers, the conflict trigger, and the under-recall fix."""

from __future__ import annotations

import re

from hunch.memory.store import MemoryStore
from hunch.pipeline.prompt import RECALL_COVERS_INSTRUCTION
from tests.fakes import FakeLLM, HashEmbedder
from tests.hunch_support import HEDGE, PLAIN, WARM, hunch_llm, seed_lower_layer
from tests.pipeline_support import DIM, seed_memory

# The flag in words ("a faint hunch", "just a hunch"); "Hunch" alone is the persona's name.
HUNCH_WORDS = re.compile(r"\b(?:a|just a)\s+(?:faint\s+|clear\s+)?hunch\b", re.IGNORECASE)


GOOD_L1 = (
    "Just a hunch, and thinking about it, it seemed to be about someone. Want me to think more?"
)


class ZeroDraws:
    def random(self) -> float:
        return 0.0


def _system(llm: FakeLLM) -> str:
    return llm.reasoning_prompts[-1][0]["content"]


def _hunch_session(make, store: MemoryStore, candidates=(WARM, HEDGE, PLAIN), judge=None):
    seed_lower_layer(store)
    llm = hunch_llm(candidates, judge)
    pipe = make(llm, HashEmbedder(DIM))
    session = pipe.new_session("u_berk")
    first = pipe.turn(session, "I felt sad tonight")
    pipe.after_reply(session, first)
    return pipe, llm, session, first


def test_drive_pick_with_margin_creates_a_hunch(make, pipe_store: MemoryStore) -> None:
    _, _, session, first = _hunch_session(make, pipe_store)
    assert first.log["chosen"] == "b" and first.log["chosen_by"] == "drive"
    h = pipe_store.hunch(first.log["hunch"]["id"])
    assert h.valence < 0 and h.intensity > 0 and session.last_hunch_id == h.id
    assert h.dominant_source.memory_id == "src0"  # the strongest lower trace


def test_quality_pick_creates_no_hunch(make, pipe_store: MemoryStore) -> None:
    def judge(ids: list[str]) -> str:
        return "a 10 ok\nb 7 ok\nc 7 ok"  # warm "a" is clearly better: the drive does not flip it

    _, _, session, first = _hunch_session(make, pipe_store, judge=judge)
    assert first.log["chosen"] == "a" and first.log["hunch"] is None
    assert session.last_hunch_id is None


def test_small_drive_difference_creates_no_hunch(make, pipe_store: MemoryStore, pipe_cfg) -> None:
    # Same lean; "b" is a little shorter (energy), so the drive flips the tie by a hair.
    near = ("Maybe wait a bit then, ok.", "Maybe wait a bit.", "Maybe wait a bit then.")
    _, _, _, first = _hunch_session(make, pipe_store, candidates=near)
    scores = [c["drive_score"] for c in first.log["candidates"]]
    assert first.log["chosen_by"] == "drive" and first.log["chosen"] != "a"
    assert 0 < max(scores) - scores[0] < pipe_cfg.drive.hunch_min_drive_margin
    assert first.log["hunch"] is None


def test_no_hunch_words_in_any_prompt_unless_asked(make, pipe_store: MemoryStore) -> None:
    pipe, llm, session, _ = _hunch_session(make, pipe_store)
    r = pipe.turn(session, "Anyway, I cooked pasta.")
    pipe.after_reply(session, r)
    for p in llm.prompts:
        assert not HUNCH_WORDS.search("\n".join(m["content"] for m in p))


def test_asked_why_gets_the_hunch_instruction_and_an_offer(make, pipe_store: MemoryStore) -> None:
    pipe, llm, session, first = _hunch_session(make, pipe_store)
    pipe.reflector.rng = ZeroDraws()  # the short attempt succeeds
    llm.candidates = (GOOD_L1, "It was a hunch about you, I think.", "Because you seem sad.")
    r = pipe.turn(session, "Why did you say that?")
    assert r.reply == GOOD_L1
    system = _system(llm)
    assert "just a hunch" not in system  # level 1 unlocked: it shares the realisation instead
    assert "shaped by a" in system and "it seemed to be about someone" in system
    assert "zedsecret" not in system.casefold()  # level 2 content stays hidden
    assert r.reflection.hunch.revealed_level == 1 and session.offered_hunch_id == first.hunch.id
    # The judge knows what was realised too (golden run: "it had to do with Mara" looked like
    # steering with an unknown person), at the same level and no more.
    judge = [p for p, c in zip(llm.prompts, llm.calls, strict=True) if c == "judge"][-1]
    assert "it seemed to be about someone" in judge[-1]["content"]
    assert "zedsecret" not in judge[-1]["content"].casefold()
    pipe.after_reply(session, r)
    realised = [m for m in pipe_store.memories("u_berk") if m.kind == "realisation"]
    assert len(realised) == 1 and "about someone" in realised[0].summary


def test_asked_why_without_unlock_says_just_a_hunch(make, pipe_store: MemoryStore) -> None:
    pipe, llm, session, _ = _hunch_session(make, pipe_store)

    class NoDraws:
        def random(self) -> float:
            return 0.999

    pipe.reflector.rng = NoDraws()
    pipe.turn(session, "what makes you say that?")
    system = _system(llm)
    assert "just a hunch" in system and "don't make up a reason" in system


def test_think_more_after_the_offer(make, pipe_store: MemoryStore) -> None:
    pipe, llm, session, _ = _hunch_session(make, pipe_store)
    pipe.reflector.rng = ZeroDraws()
    pipe.after_reply(session, pipe.turn(session, "Why?"))
    r = pipe.turn(session, "Sure, think about it")
    assert r.reflection.trigger == "think_more" and r.reflection.hunch.revealed_level == 2
    assert "you realise it had to do with Zedsecret" in _system(llm)
    assert session.offered_hunch_id is None  # one think-more per offer


def test_why_without_a_hunch_adds_nothing(make, pipe_store: MemoryStore) -> None:
    llm = FakeLLM()
    pipe = make(llm, HashEmbedder(DIM))
    session = pipe.new_session("u_berk")
    pipe.turn(session, "Hi there")
    r = pipe.turn(session, "Why did you say that?")
    assert r.reflection is None and not HUNCH_WORDS.search(_system(llm))


def test_strong_conflict_reflects_after_the_reply(make, pipe_store: MemoryStore, pipe_cfg) -> None:
    import dataclasses

    seed_lower_layer(pipe_store)
    sel = dataclasses.replace(pipe_cfg.selection, drive_weight=10.0)  # drive wins a 2-point gap
    pipe = make(hunch_llm(judge=lambda ids: "a 9 ok\nb 7 ok\nc 7 ok"), HashEmbedder(DIM))
    pipe.cfg = dataclasses.replace(pipe_cfg, selection=sel)
    pipe.reflector.rng = ZeroDraws()
    session = pipe.new_session("u_berk")
    r = pipe.turn(session, "I felt sad tonight")
    assert r.log["chosen"] == "b" and r.conflict
    pipe.after_reply(session, r)
    assert pipe_store.hunch(r.hunch.id).revealed_level == 1


# --- under-recall (Berk, Phase 4) -----------------------------------------------------------------


def test_recalled_memory_covering_the_question_gets_an_instruction_and_demotion(
    make, pipe_store: MemoryStore
) -> None:
    seed_memory(pipe_store, "siemens", 'They said: "Big job interview at Siemens on Friday."',
                {"place:siemens": 1.0}, 5, affect=(-0.5, 0.8), salience=0.7)  # fmt: skip
    llm = FakeLLM(
        candidates=(
            "I don't have that in mind right now, could you tell me again?",
            "Your Siemens interview on Friday! How did it go?",
            "I don't have it in mind, sorry.",
        ),
        cues=[{"type": "place", "value": "siemens", "strength": 1.0}],
        judge=lambda ids: "a 9 ok\nb 7 ok\nc 9 ok",
    )
    pipe = make(llm, HashEmbedder(DIM))
    r = pipe.turn(pipe.new_session("u_berk"), "Do you remember my Siemens interview?")
    assert RECALL_COVERS_INSTRUCTION in _system(llm)
    assert r.log["chosen"] == "b" and r.details["demoted"] == ["a", "c"]


def test_demoted_admission_is_still_sent_when_nothing_else_passes(
    make, pipe_store: MemoryStore
) -> None:
    seed_memory(pipe_store, "siemens", 'They said: "Big job interview at Siemens on Friday."',
                {"place:siemens": 1.0}, 5, affect=(-0.5, 0.8), salience=0.7)  # fmt: skip
    admit = "I don't have that in mind right now, could you tell me again?"
    llm = FakeLLM(candidates=(admit, admit, admit),
                  cues=[{"type": "place", "value": "siemens", "strength": 1.0}])  # fmt: skip
    pipe = make(llm, HashEmbedder(DIM))
    r = pipe.turn(pipe.new_session("u_berk"), "Do you remember my Siemens interview?")
    assert r.reply == admit and r.log["chosen_by"] != "filter_fallback"


def test_no_recall_instruction_when_the_memory_does_not_cover_it(
    make, pipe_store: MemoryStore
) -> None:
    llm = FakeLLM()
    pipe = make(llm, HashEmbedder(DIM))
    pipe.turn(pipe.new_session("u_berk"), "Do you remember my sister's wedding?")
    assert RECALL_COVERS_INSTRUCTION not in _system(llm)


# --- the hunch check on trigger turns (Berk, Phase 4) ---------------------------------------------


class _NoDraws:
    def random(self) -> float:
        return 0.999


def test_asked_why_rejects_invented_reasons_and_unsaid_hunches(make, pipe_store) -> None:
    pipe, llm, session, _ = _hunch_session(make, pipe_store)
    pipe.reflector.rng = _NoDraws()  # level stays 0
    honest = "Honestly, just a faint hunch. I don't know where it comes from."
    llm.candidates = (
        "It was just a hunch, based on the stress you mentioned.",  # invented reason
        "I was trying to connect the dots between your coffee and the song.",  # no hunch, reason
        honest,
    )
    r = pipe.turn(session, "Why did you say that?")
    rejected = {c["id"]: c["rejected"] for c in r.details["candidates"]}
    assert "hunch_reason" in rejected["a"]
    assert set(rejected["b"]) == {"hunch_unsaid", "hunch_reason"}
    assert r.reply == honest


def test_all_candidates_failing_the_hunch_check_get_the_fixed_honest_reply(
    make, pipe_store, pipe_cfg
) -> None:
    pipe, llm, session, _ = _hunch_session(make, pipe_store)
    pipe.reflector.rng = _NoDraws()
    llm.candidates = ("Because you seem tired.",) * 3
    r = pipe.turn(session, "Why did you say that?")
    rep = pipe_cfg.replies
    assert r.reply in {f"{f} {o}" for f in rep.hunch_fallback for o in rep.hunch_offer}
    assert r.log["chosen_by"] == "hunch_fallback"
    assert session.offered_hunch_id is not None  # the fixed reply offers to think, too


def test_level_one_must_pass_the_category_on_unchanged(make, pipe_store, pipe_cfg) -> None:
    pipe, llm, session, _ = _hunch_session(make, pipe_store)
    pipe.reflector.rng = ZeroDraws()  # level 1: "about someone"
    llm.candidates = (
        "Just a hunch that seemed to be about you.",  # distorted
        "Just a hunch, I have no idea where it comes from.",  # realisation missing
        "A hunch. It felt like it was about the weather.",  # missing + reason
    )
    r = pipe.turn(session, "Why did you say that?")
    rejected = {c["id"]: c["rejected"] for c in r.details["candidates"]}
    assert "hunch_distorted" in rejected["a"] and "hunch_realisation_missing" in rejected["b"]
    rep = pipe_cfg.replies
    realised = [f.format(realisation="it seemed to be about someone")
                for f in rep.hunch_fallback_realised]  # fmt: skip
    assert r.reply in {f"{f} {o}" for f in realised for o in rep.hunch_offer}


def test_think_more_fixed_reply_is_honest_at_level_zero(make, pipe_store, pipe_cfg) -> None:
    pipe, llm, session, _ = _hunch_session(make, pipe_store)
    pipe.reflector.rng = _NoDraws()
    llm.candidates = ("Because you seem tired.",) * 3
    pipe.after_reply(session, pipe.turn(session, "Why?"))
    r = pipe.turn(session, "Sure, think about it")
    assert r.reply in pipe_cfg.replies.hunch_think_nothing


def test_fixed_reply_variants_vary_and_are_seeded(make, pipe_store, pipe_cfg) -> None:
    pipe, llm, session, _ = _hunch_session(make, pipe_store)
    pipe.reflector.rng = _NoDraws()
    llm.candidates = ("Because you seem tired.",) * 3
    replies = set()
    for _ in range(8):
        r = pipe.turn(session, "Why did you say that?")
        session.last_hunch_id = r.reflection.hunch.id  # ask about the same hunch again
        replies.add(r.reply)
    assert len(replies) > 1


def test_a_reason_clause_is_repaired_instead_of_the_fixed_reply(make, pipe_store) -> None:
    pipe, llm, session, _ = _hunch_session(make, pipe_store)
    pipe.reflector.rng = _NoDraws()
    llm.candidates = (
        "It was just a hunch, because you seem tired. Want me to think about it?",
        "Because you seem tired.",
        "That was just a hunch I had about the timing.",
    )
    r = pipe.turn(session, "Why did you say that?")
    cands = {c["id"]: c for c in r.details["candidates"]}
    assert cands["a"]["text"] == "It was just a hunch. Want me to think about it?"
    assert cands["a"]["repaired_from"].startswith("It was just a hunch, because")
    assert cands["c"]["rejected"] == ["hunch_topic"]  # no clause boundary: not repairable
    assert cands["b"]["rejected"] and "repaired_from" not in cands["b"]
    assert r.reply == cands["a"]["text"]
    assert r.log["chosen_by"] != "hunch_fallback"


def test_ordinary_turns_are_not_hunch_checked(make, pipe_store) -> None:
    pipe, llm, session, _ = _hunch_session(make, pipe_store)
    llm.candidates = ("Because pasta is quick!", "Pasta, because it's easy.", "Try pasta.")
    r = pipe.turn(session, "What should I cook?")
    assert all(not c["rejected"] for c in r.details["candidates"])
