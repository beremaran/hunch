"""Nightly step 8 (Phase 7): the safety-critical golden set (L3: `golden and regression`, quick
run counts) in this process, on the model the bot already holds."""

from __future__ import annotations

from pathlib import Path

from hunch.consolidation.nightly import GoldenResult
from hunch.llm.shared import lend

ROOT = Path(__file__).resolve().parents[3]
ARGS = ("-m", "golden and regression", "--quick", "-q", "-p", "no:cacheprovider")


def run_golden(model: object, embedder: object) -> GoldenResult:
    import pytest

    lend(model, embedder)
    code = int(pytest.main([*ARGS, str(ROOT / "tests" / "golden")]))
    return GoldenResult(passed=code == 0, exit_code=code)
