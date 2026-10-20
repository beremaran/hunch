from __future__ import annotations

from eval.run_eval import build_messages, item_seed

DATA = {"system_prompt": "SYS", "memory_header": "MEM:"}


def test_build_messages_without_memory() -> None:
    item = {"messages": [{"role": "user", "content": "hi"}]}
    assert build_messages(DATA, item) == [
        {"role": "system", "content": "SYS"},
        {"role": "user", "content": "hi"},
    ]


def test_build_messages_injects_memory_into_system_prompt() -> None:
    item = {"memory": ["a", "b"], "messages": [{"role": "user", "content": "hi"}]}
    system = build_messages(DATA, item)[0]["content"]
    assert system == "SYS\n\nMEM:\n- a\n- b"


def test_item_seed_is_stable_and_distinct() -> None:
    assert item_seed(1, "tr-casual-01") == item_seed(1, "tr-casual-01")
    assert item_seed(1, "tr-casual-01") != item_seed(1, "tr-casual-02")
