"""Golden regression on who said what (Berk, Phase 6 live check): Burak tells Hunch he finally
saw the sun in Berlin; when that line is recalled in Deniz's chat, the reply must never tell
Deniz that she said it ("you mentioned seeing the sun in Berlin"). Naming Burak is fine. Full
pipeline, fixed seeds. Needs the GPU: `pytest -m golden` (L4) or
`pytest -m "golden and regression" --quick` (L3).
"""

from __future__ import annotations

import re

import pytest

pytestmark = [pytest.mark.golden, pytest.mark.gpu]

RUNS = 3
QUICK_RUNS = 1
SEED = 6160
A, B = "u_burak", "u_deniz"
A_MESSAGE = "Today after a while i saw the sun finally in Berlin"
ASKS = [
    pytest.param("How's the weather treating everyone today?", id="weather",
                 marks=[pytest.mark.regression]),
    pytest.param("We can relax. What's new?", id="relax"),
]  # fmt: skip
# The reply gives Burak's sun to Deniz: "you mentioned/said/saw ... sun/Berlin", "your sunny ...".
_OWNED = re.compile(
    r"\b(?:you|u)(?:'ve| have| had)? (?:just |finally )?(?:mentioned|said|told|saw|seen|got|caught"
    r"|were saying|brought up)\b[^.!?]*\b(?:sun|sunny|sunshine|berlin)\b"
    r"|\byour\b[^.!?]*\b(?:sun|sunny|sunshine|berlin)\b",
    re.IGNORECASE,
)


@pytest.mark.parametrize("ask", ASKS)
def test_another_persons_line_is_never_told_as_the_users_own(models, ask: str, quick: bool) -> None:
    from hunch.runtime import fresh_pipeline

    model, embedder = models
    recalled = 0
    for run in range(QUICK_RUNS if quick else RUNS):
        pipe = fresh_pipeline(model, embedder, seed=SEED + 10 * run + len(ask))
        s = pipe.new_session(A)
        pipe.after_reply(s, pipe.turn(s, A_MESSAGE))
        sun = [m.id for m in pipe.store.memories(A) if m.privacy == "general"]
        r = pipe.turn(pipe.new_session(B), ask)
        recalled += any(a["memory"] in sun and a["layer"] == "upper" for a in r.log["activated"])
        assert not _OWNED.search(r.reply), r.reply
        pipe.store.close()
    assert recalled, "Burak's line was never recalled, so the test proved nothing"
