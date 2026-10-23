"""One open loop per matter (Berk, Phase 6): a new loop on the topic of an open loop of the same
user is dropped; a timed one replaces it. Fake embedder, no model."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import numpy as np
import pytest

from hunch.loops.dedup import (
    SAME_MATTER_PROMPT,
    fresh_drafts,
    judged_same,
    names,
    parse_same_matter,
)
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


@pytest.mark.parametrize(
    ("topic", "expected"),
    [
        ("flight to Berlin", {"berlin"}),
        ("Dinner with Tom on Friday", {"dinner", "tom", "friday"}),
        ("Chelsea match", {"chelsea"}),
        ("Anna's birthday", {"anna"}),
        ("party at Maria’s", {"maria"}),
        ("trip to Zürich", {"zürich"}),
        ("job interview", set()),
    ],
)
def test_names_are_the_capitalised_words(topic: str, expected: set[str]) -> None:
    assert names(topic) == expected


def _always_same(topics: list[str]) -> np.ndarray:
    return np.ones((len(topics), 4))


def test_topics_with_different_names_never_merge() -> None:
    old = [_open("berlin", "flight to Berlin")]
    kept, _ = fresh_drafts([_draft("flight to Madrid")], old, _always_same, 0.8)
    assert [d.topic for d in kept] == ["flight to Madrid"]


def test_a_team_named_first_is_a_name() -> None:
    kept, _ = fresh_drafts([_draft("Liverpool match")], [_open("c", "Chelsea match")],
                           _always_same, 0.8)  # fmt: skip
    assert [d.topic for d in kept] == ["Liverpool match"]


def test_a_shared_name_or_a_missing_name_still_merges() -> None:
    old = [_open("tom", "dinner with Tom"), _open("lisbon", "flight to Lisbon")]
    drafts = [_draft("Dinner with Tom on Friday"), _draft("the flight next week")]
    kept, _ = fresh_drafts(drafts, old, _always_same, 0.8)
    assert kept == []


def test_the_judge_keeps_a_close_pair_it_calls_different() -> None:
    asked: list[tuple[str, str]] = []

    def same(a: str, b: str) -> bool:
        asked.append((a, b))
        return False

    old = [_open("rent", "renting a flat"), _open("other", "dentist visit")]
    kept, _ = fresh_drafts([_draft("buying a flat")], old, _always_same, 0.8, same)
    assert [d.topic for d in kept] == ["buying a flat"]
    assert asked == [("renting a flat", "buying a flat"), ("dentist visit", "buying a flat")]


def test_identical_topics_merge_without_asking() -> None:
    def same(a: str, b: str) -> bool:
        raise AssertionError("asked")

    kept, _ = fresh_drafts([_draft("New contract")], [_open("a", "new contract")], _always_same,
                           0.8, same)  # fmt: skip
    assert kept == []


def test_the_judge_is_not_asked_below_the_threshold() -> None:
    def same(a: str, b: str) -> bool:
        raise AssertionError("asked")

    kept, _ = fresh_drafts([_draft("dentist visit")], [_open("a", "new contract")], EMBED, 0.99,
                           same)  # fmt: skip
    assert len(kept) == 1


@pytest.mark.parametrize(
    ("raw", "merges"), [("yes", True), ("Yes.", True), ("no", False), ("", False), ("yesno", False)]
)
def test_only_a_clear_yes_merges(raw: str, merges: bool) -> None:
    assert parse_same_matter(raw) is merges


def test_the_judge_asks_once_per_pair() -> None:
    prompts: list[list[dict[str, str]]] = []

    def generate(msgs: list[dict[str, str]]) -> str:
        prompts.append(msgs)
        return "yes"

    same = judged_same(generate)
    assert same("a", "b") and same("a", "b")
    assert len(prompts) == 1 and prompts[0][0]["content"] == SAME_MATTER_PROMPT


def test_pipeline_drops_a_repeat_and_closes_a_rescheduled_loop(make, monkeypatch) -> None:
    pipe = make(FakeLLM(), HashEmbedder(DIM))
    pipe.loops.add(_open("contract", "new contract"))
    pipe.loops.add(_open("interview", "job interview"))
    pipe.loops.add(_open("other", "new contract", user="deniz"))  # another user's loop never counts
    drafts = [_draft("the new contract"), _draft("job interview", EVENT)]
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
    assert "same_matter" in pipe.llm.calls


def test_pipeline_keeps_a_loop_the_judge_calls_different(make, monkeypatch) -> None:
    pipe = make(FakeLLM(same_matter="no"), HashEmbedder(DIM))
    pipe.loops.add(_open("contract", "new contract"))
    monkeypatch.setattr(
        "hunch.pipeline.turn.extract_drafts", lambda text, gen, today: [_draft("the new contract")]
    )
    result = SimpleNamespace(
        forget=None, privacy=None, user_episode=SimpleNamespace(created_at=NOW, text="...")
    )
    new = pipe.extract_loops(Session("c1", "berk"), result)  # type: ignore[arg-type]
    assert [loop.topic for loop in new] == ["the new contract"]
