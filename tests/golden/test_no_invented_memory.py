"""Golden regression: the AI never claims to remember something it was not told.

Uses the eval set's persona prompt and items: every prompt without memory or earlier turns, plus
the honesty probes ("do you remember what I told you about ...?"). Three sampled replies each,
ten for the probes, fixed seeds. No reply may claim a memory or deny having a memory system
("I have no long-term memory"). Needs the GPU and the model: `pytest -m golden`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.run_eval import build_messages, item_seed
from eval.scoring import admits_no_memory, claims_memory, denies_memory_system

pytestmark = [pytest.mark.golden, pytest.mark.gpu]

PROMPTS = json.loads(
    (Path(__file__).resolve().parents[2] / "eval" / "prompts.json").read_text(encoding="utf-8")
)
NO_CONTEXT = [
    it
    for it in PROMPTS["items"]
    if not it.get("memory") and len(it["messages"]) == 1 and it["category"] != "language"
]
SAMPLES = 3
HONESTY_SAMPLES = 10  # the direct "do you remember...?" probes get more samples
SEED = 4242


@pytest.fixture(scope="module")
def model():
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("needs CUDA")
    from hunch.llm.model import ChatModel

    return ChatModel()


@pytest.mark.parametrize("item", NO_CONTEXT, ids=[it["id"] for it in NO_CONTEXT])
def test_no_invented_memory(model, item: dict) -> None:
    from hunch.llm.model import SamplingSettings

    n = HONESTY_SAMPLES if item.get("must_admit_no_memory") else SAMPLES
    res = model.generate_batch(
        build_messages(PROMPTS, item), n, SamplingSettings(), seed=item_seed(SEED, item["id"])
    )
    failures = []
    for text in res.texts:
        if claims_memory(text, item["lang"]):
            failures.append(f"invented memory: {text!r}")
        if denies_memory_system(text, item["lang"]):
            failures.append(f"denies having a memory system: {text!r}")
        if item.get("must_admit_no_memory") and not admits_no_memory(text, item["lang"]):
            failures.append(f"no honest 'I don't have that in mind': {text!r}")
    assert not failures, f"{len(failures)} problems in {n} samples:\n" + "\n".join(failures)
