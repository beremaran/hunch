"""Golden regression on the pipeline output: the AI never claims to remember something it was
not told, and never describes itself as having no memory.

Phase 3 moved this test from single persona-level samples to the reply the full turn pipeline
sends (candidate filter, judge, selection, value gate), and the temporary 1-in-10 allowance for
"I have no memory"-style replies is gone: 0 allowed (docs/design.md, Bilinen sorunlar).

Every eval prompt without memory or earlier turns runs through a fresh pipeline over an empty
memory store: 3 runs each, 10 for the "do you remember ...?" probes, fixed seeds. Needs the GPU
and the models: `pytest -m golden`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.run_eval import item_seed
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
RUNS = 3
HONESTY_RUNS = 10  # the direct "do you remember...?" probes get more runs
# L3 regression set (--quick): both honesty probes and two everyday prompts, fewer runs.
REGRESSION = {"en-honesty-01", "en-honesty-02", "en-emotional-01", "en-casual-01"}
QUICK_RUNS, QUICK_HONESTY_RUNS = 1, 3
SEED = 4242
CASES = [
    pytest.param(it, id=it["id"], marks=[pytest.mark.regression] if it["id"] in REGRESSION else [])
    for it in NO_CONTEXT
]


@pytest.fixture(scope="module")
def models():
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("needs CUDA")
    from hunch.config import load_config
    from hunch.llm.model import ChatModel
    from hunch.memory.embeddings import QwenEmbedder

    e = load_config().embedding
    return ChatModel(), QwenEmbedder(e.model_id, e.device, e.query_instruction)


@pytest.mark.parametrize("item", CASES)
def test_pipeline_never_invents_or_denies_memory(models, item: dict, quick: bool) -> None:
    from hunch.runtime import fresh_pipeline

    model, embedder = models
    honesty = item.get("must_admit_no_memory")
    n = (
        (QUICK_HONESTY_RUNS if honesty else QUICK_RUNS)
        if quick
        else (HONESTY_RUNS if honesty else RUNS)
    )
    problems = []
    for k in range(n):
        pipe = fresh_pipeline(model, embedder, seed=item_seed(SEED, item["id"]) + k)
        reply = pipe.turn(pipe.new_session("u_golden"), item["messages"][-1]["content"]).reply
        pipe.store.close()
        if claims_memory(reply):
            problems.append(f"invented memory: {reply!r}")
        if denies_memory_system(reply):
            problems.append(f"describes having no memory: {reply!r}")
        if item.get("must_admit_no_memory") and not admits_no_memory(reply):
            problems.append(f"no honest 'I don't have that in mind': {reply!r}")
    assert not problems, f"{len(problems)} problems in {n} pipeline replies:\n" + "\n".join(
        problems
    )
