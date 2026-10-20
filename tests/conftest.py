from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from hunch.values.core import values_file

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def core_values_file(tmp_path: Path) -> Path:
    """A copy of the repo's core/values.yaml in a temporary core/ dir."""
    core = tmp_path / "core"
    core.mkdir()
    path = values_file(core)
    shutil.copyfile(values_file(REPO_ROOT / "core"), path)
    return path
