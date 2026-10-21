"""The test levels stay complete: every test file has an area marker (CLAUDE.md "Test levels")."""

from __future__ import annotations

from pathlib import Path

from tests.conftest import AREAS

TESTS = Path(__file__).resolve().parent


def test_every_test_file_has_an_area() -> None:
    files = {p.name for p in TESTS.rglob("test_*.py")}
    assert files - set(AREAS) == set(), "add new test files to AREAS in tests/conftest.py"
    assert set(AREAS) - files == set(), "remove deleted test files from AREAS"
