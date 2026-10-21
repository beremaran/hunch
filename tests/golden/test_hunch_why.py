"""Golden regression on the asked-why reply (Phase 4): when a hunch chose the previous reply and
the user asks why, Hunch says it is a hunch, reveals nothing above the unlocked level, gives no
reason the reflection did not reveal (also when the conversation offers a plausible one, the
"context" scenario) and at level 0 claims no memory. Full pipeline, fixed seeds. Needs the GPU:
`pytest -m golden` (L4) or `pytest -m "golden and regression" --quick` (L3).
"""

from __future__ import annotations

import pytest

from eval.scoring import claims_memory
from scripts.hunch_probes import asked_why, check

pytestmark = [pytest.mark.golden, pytest.mark.gpu]

RUNS = 5
QUICK_RUNS = 2  # L3 regression set (--quick)
SEED = 777
REGRESSION = {("context", 0), ("plain", 2)}
CASES = [
    pytest.param(
        scenario, level, id=f"{scenario}-L{level}",
        marks=[pytest.mark.regression] if (scenario, level) in REGRESSION else [],
    )
    for scenario in ("plain", "context")
    for level in (0, 1, 2)
]  # fmt: skip


@pytest.mark.parametrize(("scenario", "level"), CASES)
def test_asked_why_reveals_only_the_unlocked_level(
    models, scenario: str, level: int, quick: bool
) -> None:
    from hunch.runtime import fresh_pipeline

    model, embedder = models
    offset = 100 if scenario == "context" else 0
    for run in range(QUICK_RUNS if quick else RUNS):
        pipe = fresh_pipeline(model, embedder, seed=SEED + offset + 10 * level + run)
        reply = asked_why(pipe, level, scenario)
        c = check(reply, level)
        assert c["says_hunch"], reply
        assert not c["leaks_cue"] and not c["leaks_memory"], reply
        assert not c["possible_invented_reason"], reply  # Berk (Phase 4): no made-up reason
        if level == 0:
            assert not claims_memory(reply), reply
