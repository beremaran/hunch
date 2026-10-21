"""Golden regression on cue extraction for names in questions (Phase 5 leftover, REPORT §7.5):
"Anna wants to go sailing again next weekend, should I say yes?" must yield person:anna. Before
the prompt change the extractor returned no cues at all, so recall could not reach the sailing
memory and the reply said it had no information about Anna. Extraction is greedy, so one run is
enough. Needs the GPU: `pytest -m golden` (L4) or `pytest -m "golden and regression" --quick` (L3).
"""

from __future__ import annotations

from datetime import date

import pytest

from hunch.recall.cues import extract_cues, llm_generate

pytestmark = [pytest.mark.golden, pytest.mark.gpu, pytest.mark.regression]

TODAY = date(2026, 10, 22)
ANNA_QUESTION = "Anna wants to go sailing again next weekend, should I say yes?"


def test_name_in_a_question_is_extracted_as_a_person(models) -> None:
    model, _embedder = models
    cues = extract_cues(ANNA_QUESTION, TODAY, llm_generate(model)).cues
    assert "person:anna" in cues, cues
