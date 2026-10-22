"""One open loop per matter (Berk, Phase 6): a new loop on the topic of an open loop of the same
user is dropped; a timed one replaces it. Fake embedder, no model."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from hunch.loops.dedup import fresh_drafts
from hunch.loops.extract import LoopDraft
from hunch.loops.store import OpenLoop
from hunch.pipeline.turn import Session
from tests.fakes import FakeLLM, HashEmbedder
from tests.pipeline_support import DIM

NOW = datetime(2026, 10, 22, 12, 0).timestamp()
EMBED = HashEmbedder(64).embed_documents
EVENT = datetime(2026, 10, 29, 14, 0)


def _open(loop_id: str, topic: str, user: str = "berk") -> OpenLoop:
    return OpenLoop(loop_id, user, topic, "said", "How did it go?", "general", NOW + 86400,
                    created_at=NOW)  # fmt: skip


def _draft(topic: str, event_at: datetime | None = None) -> LoopDraft:
    return LoopDraft(topic, "said", "How did it go?", 7, event_at=event_at)


def test_a_new_topic_is_kept() -> None:
    kept, replaced = fresh_drafts([_draft("dentist visit")], [_open("a", "new contract")],
                                  EMBED, 0.75)  # fmt: skip
    assert [d.topic for d in kept] == ["dentist visit"] and replaced == []


def test_the_same_matter_again_is_dropped() -> None:
    kept, replaced = fresh_drafts([_draft("the new contract")], [_open("a", "new contract")],
                                  EMBED, 0.75)  # fmt: skip
    assert kept == [] and replaced == []


def test_a_timed_draft_replaces_the_old_loops() -> None:
    old = [_open("wish", "job interview"), _open("after", "job interview")]
    kept, replaced = fresh_drafts([_draft("job interview", EVENT)], old, EMBED, 0.75)
    assert [d.topic for d in kept] == ["job interview"]
    assert replaced == ["wish", "after"]


def test_two_drafts_of_one_message_on_the_same_matter_give_one_loop() -> None:
    kept, _ = fresh_drafts([_draft("new contract"), _draft("new contract")], [], EMBED, 0.75)
    assert len(kept) == 1


def test_without_an_embedder_only_exact_topics_match() -> None:
    old = [_open("a", "New contract")]
    kept, _ = fresh_drafts([_draft("new contract"), _draft("the new contract")], old, None, 0.75)
    assert [d.topic for d in kept] == ["the new contract"]


def test_pipeline_drops_a_repeat_and_closes_a_rescheduled_loop(make, monkeypatch) -> None:
    pipe = make(FakeLLM(), HashEmbedder(DIM))
    pipe.loops.add(_open("contract", "new contract"))
    pipe.loops.add(_open("interview", "job interview"))
    pipe.loops.add(_open("other", "new contract", user="deniz"))  # another user's loop never counts
    drafts = [_draft("new contract"), _draft("job interview", EVENT)]
    monkeypatch.setattr("hunch.pipeline.turn.extract_drafts", lambda text, gen, today: drafts)
    result = SimpleNamespace(
        forget=None, privacy=None, user_episode=SimpleNamespace(created_at=NOW, text="...")
    )
    new = pipe.extract_loops(Session("c1", "berk"), result)  # type: ignore[arg-type]
    assert {loop.topic for loop in new} == {"job interview"}
    assert pipe.loops.get("contract").status == "open"
    assert pipe.loops.get("interview").status == "closed"
    assert pipe.loops.get("other").status == "open"
    assert all(loop.user == "deniz" for loop in pipe.loops.open_for("deniz"))
