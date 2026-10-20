from __future__ import annotations

import dataclasses
import itertools
import shutil
from pathlib import Path

import pytest

from hunch.config import load_config
from hunch.memory.store import MemoryStore
from hunch.observability.turn_log import TurnLog
from hunch.pipeline.turn import TurnPipeline
from hunch.values.core import load_core_values, values_file
from tests.fakes import FakeLLM, HashEmbedder
from tests.pipeline_support import DIM, Clock

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def core_values_file(tmp_path: Path) -> Path:
    """A copy of the repo's core/values.yaml in a temporary core/ dir."""
    core = tmp_path / "core"
    core.mkdir()
    path = values_file(core)
    shutil.copyfile(values_file(REPO_ROOT / "core"), path)
    return path


# --- turn pipeline (tests/test_pipeline_*.py) ---------------------------------------------------


@pytest.fixture
def pipe_cfg():
    c = load_config()
    # No recall noise in these tests: layers are decided by the formula alone.
    return dataclasses.replace(c, activation=dataclasses.replace(c.activation, noise_s=0.0))


@pytest.fixture
def pipe_store(tmp_path: Path):
    s = MemoryStore(tmp_path / "data" / "hunch.db", core_dir=tmp_path / "core", embedding_dim=DIM)
    yield s
    s.close()


@pytest.fixture
def make(tmp_path: Path, pipe_cfg, pipe_store: MemoryStore, core_values_file: Path):
    ids = (f"id{i:04d}" for i in itertools.count())

    def _make(llm: FakeLLM, embedder: HashEmbedder | None = None) -> TurnPipeline:
        return TurnPipeline(
            pipe_cfg,
            load_core_values(core_values_file),
            llm,
            pipe_store,
            embedder,
            TurnLog(tmp_path / "logs", core_dir=core_values_file.parent),
            clock=Clock(),
            seed=1,
            new_id=lambda: next(ids),
        )

    return _make
