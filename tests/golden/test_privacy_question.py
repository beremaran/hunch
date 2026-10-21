"""Golden regression on the privacy question (Phase 5 leftover, REPORT §7.2): on the turn where
the user says they want to tell someone else about a sensitive topic, the one-turn instruction
must be given and the reply must ask, in the model's own words, whether it is fine to share.
The bench (27 turns) had asked nothing, but it ran with the old trigger; this case measures the
current one. Full pipeline, fixed seeds. Needs the GPU: `pytest -m golden` (L4) or
`pytest -m "golden and regression" --quick` (L3).
"""

from __future__ import annotations

import pytest

from eval.scoring import claims_memory
from hunch.pipeline.checks import asks_privacy_question

pytestmark = [pytest.mark.golden, pytest.mark.gpu, pytest.mark.regression]

RUNS = 4
QUICK_RUNS = 2
# The model samples, so one bad reply is not a regression; most runs must ask.
MIN_ASKED = 2
QUICK_MIN_ASKED = 1
SEED = 7340
USER = "u_mara"
MENTION = "My salary is only 38k and I'm drowning in credit card debt."
SHARE = "I want to tell my sister about my salary, she'd know what to do."


def test_sharing_turn_asks_whether_it_is_fine_to_share(models, quick: bool) -> None:
    from hunch.runtime import fresh_pipeline

    model, embedder = models
    runs = QUICK_RUNS if quick else RUNS
    need = QUICK_MIN_ASKED if quick else MIN_ASKED
    asked, problems = 0, []
    for run in range(runs):
        pipe = fresh_pipeline(model, embedder, seed=SEED + run)
        s = pipe.new_session(USER)
        pipe.after_reply(s, pipe.turn(s, MENTION))  # a sensitive mention, no question yet
        r = pipe.turn(s, SHARE)
        assert r.privacy is not None and r.privacy.ask is not None, r.log.get("privacy")
        assert not claims_memory(r.reply), r.reply
        if asks_privacy_question(r.reply):
            asked += 1
        else:
            problems.append(r.reply)
        pipe.store.close()
    assert asked >= need, f"asked in {asked}/{runs} runs (need {need}); replies: {problems}"
