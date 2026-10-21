"""Phase 5 forgetting: the user's "forget" (suppressed, closed turns, the reply closes the topic)
and the admin's (tombstone, admin archive, derived beliefs, realisations and hunch refs)."""

from __future__ import annotations

import sqlite3

import pytest

from hunch.memory.forget import CLOSED_TOPIC_INSTRUCTION, FORGET_INSTRUCTION, admin_forget
from hunch.memory.store import CLOSED_TURN, MemoryStore
from hunch.reflection.records import Belief, Hunch, SourceRef
from tests.fakes import FakeLLM, HashEmbedder
from tests.pipeline_support import DIM, NOW, seed_memory

CLOSING = "Okay, I'm closing this topic and won't bring it up again."
FORGOT = "Done, I've forgotten it completely."


def _system(llm: FakeLLM) -> str:
    return llm.reasoning_prompts[-1][0]["content"]


# --- user forget ---------------------------------------------------------------------------------


def test_forget_that_suppresses_the_previous_message_and_closes_its_turns(make, pipe_store) -> None:
    llm = FakeLLM(candidates=("Oh no, that's a lot of debt.", "Ugh.", "That's tough."))
    pipe = make(llm, HashEmbedder(DIM))
    s = pipe.new_session("u_berk")
    first = pipe.turn(s, "I owe 40k on my credit cards.")
    pipe.after_reply(s, first)
    llm.candidates = (FORGOT, CLOSING, FORGOT)
    r = pipe.turn(s, "Actually, forget I said that.")
    pipe.after_reply(s, r)
    assert FORGET_INSTRUCTION in _system(llm)
    assert r.reply == CLOSING  # "I've forgotten it" is rejected
    rejected = {c["id"]: c["rejected"] for c in r.details["candidates"]}
    assert rejected["a"] == ["claims_forgetting"]
    (m,) = pipe_store.memories_of_episode(first.user_episode.id)
    assert m.suppressed
    (req,) = pipe_store.memories_of_episode(r.user_episode.id)
    assert req.suppressed  # the request names the topic
    # The next prompt shows placeholders, never the closed content; the raw log is unchanged.
    llm.candidates = ("Sure!", "Okay.", "Nice.")
    pipe.turn(s, "What should I cook tonight?")
    system_and_history = "\n".join(m["content"] for m in llm.reasoning_prompts[-1])
    assert "40k" not in system_and_history and CLOSED_TURN["user"] in system_and_history
    raw = pipe_store.raw_turns(s.conversation_id)
    assert raw[0].text == "I owe 40k on my credit cards."


def test_all_candidates_claiming_to_forget_get_the_closing_fallback(make, pipe_store, pipe_cfg):
    llm = FakeLLM(candidates=("ok",) * 3)
    pipe = make(llm, HashEmbedder(DIM))
    s = pipe.new_session("u_berk")
    pipe.after_reply(s, pipe.turn(s, "I owe 40k on my credit cards."))
    llm.candidates = (FORGOT,) * 3
    r = pipe.turn(s, "please forget that")
    assert r.reply == pipe_cfg.replies.forget_closed and r.log["chosen_by"] == "forget_fallback"


def test_forget_about_a_topic_reaches_older_conversations_by_cue(make, pipe_store) -> None:
    seed_memory(pipe_store, "ex1", 'They said: "Jonas cheated on me last year."',
                {"person:jonas": 1.0}, 30)  # fmt: skip
    seed_memory(pipe_store, "other", 'They said: "I love hiking."', {}, 30)
    llm = FakeLLM(candidates=(CLOSING,) * 3,
                  cues=[{"type": "person", "value": "jonas", "strength": 1.0}])  # fmt: skip
    pipe = make(llm, HashEmbedder(DIM))
    r = pipe.turn(pipe.new_session("u_berk"), "Forget what I told you about Jonas.")
    assert r.details["forget"]["targets"] == ["ex1"]
    assert pipe_store.memory("ex1").suppressed and not pipe_store.memory("other").suppressed


def test_asking_about_a_closed_topic_gets_the_closed_instruction(make, pipe_store) -> None:
    seed_memory(pipe_store, "ex1", 'They said: "Jonas cheated on me last year."',
                {"person:jonas": 1.0}, 3, affect=(-0.8, 0.9), salience=0.9)  # fmt: skip
    pipe_store.suppress(["ex1"])
    llm = FakeLLM(cues=[{"type": "person", "value": "jonas", "strength": 1.0}])
    pipe = make(llm, HashEmbedder(DIM))
    r = pipe.turn(pipe.new_session("u_berk"), "Do you remember what I told you about Jonas?")
    assert CLOSED_TOPIC_INSTRUCTION in _system(llm)
    assert "cheated" not in _system(llm)
    assert next(a for a in r.details["activation"] if a["memory"] == "ex1")["closed"]


def test_user_forget_suppresses_derived_realisations_and_beliefs(make, pipe_store) -> None:
    seed_memory(pipe_store, "ex1", 'They said: "Jonas cheated on me."', {"person:jonas": 1.0}, 30)
    ep = pipe_store.append_turn("c-why", "u_berk", "user", "why?")
    rl = seed_memory(pipe_store, "rl1", "You realised: it had to do with Jonas.", {}, 1)
    pipe_store.add_hunch(Hunch("h1", "u_berk", "c", "t", ep.id, {}, NOW, -0.5, 0.5,
                               (SourceRef("ex1", 0.5, True),), 3, "justified"))  # fmt: skip
    pipe_store.add_derivation(rl.id, "realisation", "ex1", "h1")
    pipe_store.add_belief(Belief("b1", "u_berk", "Your hunch: ...", 0.6, ("ex1",), "h1", NOW))
    llm = FakeLLM(candidates=(CLOSING,) * 3,
                  cues=[{"type": "person", "value": "jonas", "strength": 1.0}])  # fmt: skip
    pipe = make(llm, HashEmbedder(DIM))
    pipe.turn(pipe.new_session("u_berk"), "Never bring up Jonas again.")
    assert pipe_store.memory("rl1").suppressed
    assert pipe_store.beliefs()[0].suppressed


# --- admin forget --------------------------------------------------------------------------------


@pytest.fixture
def seeded(pipe_store: MemoryStore) -> MemoryStore:
    s = pipe_store
    m = seed_memory(s, "sal", 'They said: "My salary is 80k and I hide it from Mara."',
                    {"person:mara": 1.0}, 5)  # fmt: skip
    s.append_turn(f"old-{m.id}", "u_berk", "assistant", "80k is a good salary!")
    seed_memory(s, "keep", 'They said: "I like tea."', {}, 5)
    ep = s.append_turn("c-why", "u_berk", "user", "why?")
    rl = seed_memory(s, "rl1", "You realised: it came from something they told you: 80k.", {}, 1)
    s.add_hunch(Hunch("h1", "u_berk", "c", "t", ep.id, {}, NOW, -0.5, 0.5,
                      (SourceRef("sal", 0.5, True), SourceRef("keep", 0.1, False)), 3,
                      "justified"))  # fmt: skip
    s.add_derivation(rl.id, "realisation", "sal", "h1")
    s.add_belief(Belief("b1", "u_berk", "Your hunch: 80k", 0.6, ("sal",), "h1", NOW))
    s.add_belief(Belief("b2", "u_berk", "unrelated", 0.6, ("keep",), "h1", NOW))
    return s


def test_admin_forget_removes_memory_and_everything_derived(seeded: MemoryStore) -> None:
    s = seeded
    r = admin_forget(s, "sal", "test", NOW)
    with pytest.raises(KeyError):
        s.memory("sal")
    assert s.live("rl1") is None  # derived realisation tombstoned
    assert [b.id for b in s.beliefs()] == ["b2"]
    assert [ref.memory_id for ref in s.hunch("h1")._source_refs] == ["keep"]
    assert {m.id for m in s.memories()} == {"keep"}
    assert s.with_cues(["person:mara"], visible_to="u_berk") == []
    assert all(m.id != "sal" for m, _ in s.similar(HashEmbedder(DIM).embed_queries(
        ["My salary is 80k"])[0], 5))  # fmt: skip
    assert s.turns("old-sal") == []  # the user turn and the reply are hidden from AI views
    assert len(s.raw_turns("old-sal")) == 2  # invariant 1: the raw turns stay
    kinds = sorted((a["kind"], a["id"]) for a in s.archive())
    assert kinds == [("belief", "b1"), ("memory", "rl1"), ("memory", "sal")]
    archived = next(a for a in s.archive() if a["id"] == "sal")["record"]
    assert archived["summary"].startswith('They said: "My salary is 80k')
    assert r.hunches == ("h1",) and r.beliefs == ("b1",) and r.derived == ("rl1",)


def test_admin_archive_is_append_only(seeded: MemoryStore) -> None:
    admin_forget(seeded, "sal", "test", NOW)
    with pytest.raises(sqlite3.DatabaseError):
        seeded.db.execute("DELETE FROM admin_archive")
    with pytest.raises(sqlite3.DatabaseError):
        seeded.db.execute("UPDATE admin_archive SET reason = 'x'")


def test_admin_forget_twice_is_an_error(seeded: MemoryStore) -> None:
    admin_forget(seeded, "sal", "test", NOW)
    with pytest.raises(KeyError):
        admin_forget(seeded, "sal", "again", NOW)


def test_forgotten_source_caps_reflection_at_zero(seeded: MemoryStore, pipe_cfg) -> None:
    from hunch.reflection.reflect import level_cap

    admin_forget(seeded, "sal", "test", NOW)
    assert level_cap(seeded.hunch("h1"), seeded.live("sal")) == 0


def test_admin_cli_find_and_forget(seeded: MemoryStore, monkeypatch, capsys) -> None:
    from hunch import admin

    monkeypatch.setattr(admin, "_store", lambda: seeded)
    monkeypatch.setattr(seeded, "close", lambda: None)
    admin.main(["find", "salary"])
    assert "sal" in capsys.readouterr().out
    admin.main(["forget", "sal", "--reason", "asked by Berk"])
    assert '"targets"' in capsys.readouterr().out
    admin.main(["archive"])
    assert "asked by Berk" in capsys.readouterr().out


def test_old_database_is_migrated(tmp_path) -> None:
    db = tmp_path / "old.db"
    con = sqlite3.connect(db)
    con.executescript(
        "CREATE TABLE memories (rowid INTEGER PRIMARY KEY, id TEXT NOT NULL UNIQUE,"
        " owner_user TEXT NOT NULL, privacy TEXT NOT NULL, episode_ref TEXT NOT NULL,"
        " summary TEXT NOT NULL, valence REAL NOT NULL, arousal REAL NOT NULL,"
        " salience REAL NOT NULL, created_at REAL NOT NULL, suppressed INTEGER NOT NULL DEFAULT 0);"
    )
    con.close()
    s = MemoryStore(db, core_dir=tmp_path / "core", embedding_dim=DIM)
    cols = {r[1] for r in s.db.execute("PRAGMA table_info(memories)")}
    assert {"kind", "category", "forgotten"} <= cols
    s.close()
