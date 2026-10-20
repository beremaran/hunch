from __future__ import annotations

from eval.run_eval import build_messages, item_seed, summarize

DATA = {"system_prompt": "SYS", "memory_header": "MEM:", "instruction_header": "NOW:"}


def test_build_messages_without_memory() -> None:
    item = {"messages": [{"role": "user", "content": "hi"}]}
    assert build_messages(DATA, item) == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "hi"},
    ]


def test_build_messages_injects_memory_and_turn_instructions() -> None:
    item = {
        "memory": ["a", "b"],
        "turn_instructions": ["ask x"],
        "messages": [{"role": "user", "content": "hi"}],
    }
    system = build_messages(DATA, item)[0]["content"]
    assert system == "SYS\n\nMEM:\n- a\n- b\n\nNOW:\n- ask x"


def test_item_seed_is_stable_and_distinct() -> None:
    assert item_seed(1, "de-casual-01") == item_seed(1, "de-casual-01")
    assert item_seed(1, "de-casual-01") != item_seed(1, "de-casual-02")


def _row(item_id: str, sample: int, flags: list[str], latency: float) -> dict:
    return {
        "id": item_id,
        "lang": item_id[:2],
        "sample": sample,
        "reply": "r",
        "batch_latency_s": latency,
        "checks": {"flags": flags},
    }


def test_expected_fail_rows_are_listed_but_not_counted() -> None:
    rows = [
        _row("de-a", 0, [], 4.0),
        {**_row("en-lang", 0, ["wrong_lang(de)"], 4.0), "expected_fail": True},
    ]
    text = summarize(rows)
    assert "| en |" not in text
    assert "- en-lang: 0/1 clean" in text


def test_summary_counts_samples_and_latency_budget() -> None:
    rows = [
        _row("de-a", 0, [], 4.0),
        _row("de-a", 1, ["invented_memory"], 4.0),
        _row("en-b", 0, ["missing(german)"], 12.0),
    ]
    text = summarize(rows)
    assert "| de | 1 | 2 | 1 |" in text
    assert "1/2 over the 10 s budget" in text
    assert "### de-a (1/2 clean, 4.0 s)" in text
