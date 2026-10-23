"""Nightly step 6b (Phase 7): filler fades, meaningful stays, each memory is judged once."""

from __future__ import annotations

from hunch.consolidation.filler import build_filler_messages, label_filler, parse_filler
from hunch.memory.store import MemoryStore
from tests.pipeline_support import DAY, NOW, seed_memory


def _model(answers: dict[str, str]):
    asked: list[str] = []

    def generate(messages) -> str:
        user = messages[-1]["content"]
        asked.append(user)
        return next((a for key, a in answers.items() if key in user), "meaningful")

    generate.asked = asked  # type: ignore[attr-defined]
    return generate


def test_only_a_clear_filler_answer_fades() -> None:
    assert parse_filler("filler") and parse_filler(" Filler.") and parse_filler("Small talk")
    assert (
        not parse_filler("meaningful") and not parse_filler("not filler") and not parse_filler("")
    )


def test_the_question_before_is_part_of_the_judgement() -> None:
    msgs = build_filler_messages("yes", "Did you get the job?")
    assert "had just said: Did you get the job?" in msgs[-1]["content"]
    assert "had just said" not in build_filler_messages("hey", None)[-1]["content"]


def test_filler_fades_and_each_memory_is_labelled_once(pipe_store: MemoryStore, pipe_cfg) -> None:
    seed_memory(pipe_store, "hey", 'They said: "hey"', {}, 0.2)
    seed_memory(pipe_store, "wife", 'They said: "say hi to my wife"', {}, 0.2)
    seed_memory(pipe_store, "old", 'They said: "ok"', {}, 3)  # before tonight's window
    model = _model({"hey": "filler"})

    result = label_filler(pipe_store, model, pipe_cfg.nightly, NOW - DAY, NOW)

    assert result.summary() == {"labelled": 2, "faded": 1}
    assert pipe_store.memory("hey").salience == 0.2 * pipe_cfg.nightly.filler_salience_factor
    assert pipe_store.memory("wife").salience == 0.2
    assert pipe_store.memory("old").salience == 0.2
    again = label_filler(pipe_store, model, pipe_cfg.nightly, NOW - DAY, NOW + 60)
    assert again.labelled == 0 and len(model.asked) == 2


def test_a_suppressed_memory_is_never_judged(pipe_store: MemoryStore, pipe_cfg) -> None:
    seed_memory(pipe_store, "s", 'They said: "hey"', {}, 0.2)
    pipe_store.db.execute("UPDATE memories SET suppressed = 1 WHERE id = 's'")
    pipe_store.db.commit()
    model = _model({})
    assert label_filler(pipe_store, model, pipe_cfg.nightly, NOW - DAY, NOW).labelled == 0


def test_context_can_rescue_a_short_answer_but_never_condemn(pipe_store, pipe_cfg) -> None:
    def turn(conv: str, hunch: str, user: str, mid: str) -> None:
        pipe_store.append_turn(conv, "u_berk", "assistant", hunch, at=NOW - 200)
        seed_memory(pipe_store, mid, f'They said: "{user}"', {}, 0.1)
        ep = pipe_store.append_turn(conv, "u_berk", "user", user, at=NOW - 100)
        pipe_store.db.execute("UPDATE memories SET episode_ref = ? WHERE id = ?", (ep.id, mid))
        pipe_store.db.commit()

    turn("c1", "Did you get the job?", "yes", "yes")
    turn("c2", "Good luck with the move!", "Ill be unemployed in November. bye", "jobless")

    def model(messages) -> str:
        user = messages[-1]["content"]
        if "had just said" not in user:
            return "filler" if "yes" in user else "meaningful"
        return "meaningful" if "Did you get the job?" in user else "filler"

    result = label_filler(pipe_store, model, pipe_cfg.nightly, NOW - DAY, NOW)
    assert result.faded == ()  # "yes" rescued by its question; the news never condemned
