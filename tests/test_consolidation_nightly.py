"""The nightly runner (Phase 7): the gate, the order of steps, rollback, the report."""

from __future__ import annotations

import dataclasses
from datetime import datetime
from pathlib import Path

import pytest

from hunch.channels.store import ChannelStore
from hunch.consolidation.nightly import (
    STEPS,
    Decision,
    GoldenResult,
    Night,
    gate,
    nightly_tick,
    run_night,
)
from tests.fakes import FakeLLM, HashEmbedder
from tests.pipeline_support import DIM, NOW, seed_memory


@pytest.mark.parametrize(
    ("hour", "minute", "gpu", "expected"),
    [
        (0, 30, 0.5, Decision.START),
        (3, 0, None, Decision.START),  # no CUDA: nothing to wait for
        (0, 10, 0.5, Decision.SKIP),  # before the start time
        (1, 0, 9.0, Decision.RETRY),  # a game holds the GPU
        (5, 45, 9.0, Decision.SKIP),  # busy, and no time left to retry
        (7, 0, 0.5, Decision.SKIP),  # morning: too late
        (23, 50, 0.5, Decision.SKIP),
    ],
)
def test_gate(hour: int, minute: int, gpu: float | None, expected: Decision, pipe_cfg) -> None:
    now = datetime(2026, 10, 24, hour, minute)
    assert gate(now, gpu, pipe_cfg.nightly) is expected


def test_steps_run_in_design_order() -> None:
    assert [name.split()[0] for name, _ in STEPS] == ["5", "6", "6b", "7"]


def _night(make, pipe_store, pipe_cfg, tmp_path: Path, golden=None) -> Night:
    pipe = make(FakeLLM(), HashEmbedder(DIM))
    return Night(pipe, ChannelStore(pipe_store.db), pipe_cfg, NOW - 86_400, NOW,
                 tmp_path / "data", tmp_path / "logs", golden=golden)  # fmt: skip


def _repeats(pipe_store) -> None:
    for i, age in enumerate((2, 1)):
        seed_memory(pipe_store, f"r{i}", 'They said: "what folders can you access?"', {}, age)


def test_a_good_night_keeps_its_work_and_writes_the_report(make, pipe_store, pipe_cfg, tmp_path):
    _repeats(pipe_store)
    night = _night(make, pipe_store, pipe_cfg, tmp_path, lambda: GoldenResult(True, 0))
    report = run_night(night)
    assert report.ok and report.steps["6 repeats and fading"]["repeats"] == 1
    assert pipe_store.memory("r1").salience < 0.2
    text = next((tmp_path / "logs" / "nightly").glob("*.md")).read_text(encoding="utf-8")
    assert "Status: ok." in text and "Not built yet" in text


def test_a_failed_golden_set_rolls_the_night_back(make, pipe_store, pipe_cfg, tmp_path) -> None:
    _repeats(pipe_store)
    night = _night(make, pipe_store, pipe_cfg, tmp_path, lambda: GoldenResult(False, 1))
    report = run_night(night)
    assert report.rolled_back and not report.ok
    assert pipe_store.memory("r1").salience == 0.2 and not pipe_store.repeat_ids()


def test_a_failing_step_rolls_back_and_stops(make, pipe_store, pipe_cfg, tmp_path) -> None:
    _repeats(pipe_store)
    ran = []

    def boom(night):
        raise RuntimeError("model ran out of memory")

    steps = (STEPS[1], ("x broken", boom), ("y after", lambda n: ran.append(1) or {}))
    report = run_night(_night(make, pipe_store, pipe_cfg, tmp_path), steps)
    assert report.failed_step == "x broken" and "out of memory" in (report.error or "")
    assert report.rolled_back and ran == []
    assert pipe_store.memory("r1").salience == 0.2


def test_only_the_newest_snapshots_are_kept(make, pipe_store, pipe_cfg, tmp_path) -> None:
    cfg = dataclasses.replace(pipe_cfg, nightly=dataclasses.replace(pipe_cfg.nightly,
                                                                    snapshots_kept=2))  # fmt: skip
    for i in range(4):
        night = _night(make, pipe_store, cfg, tmp_path)
        run_night(dataclasses.replace(night, now=NOW + i * 86_400))
    assert len(list((tmp_path / "data" / "snapshots").glob("hunch-*.db"))) == 2


def test_tick_retries_while_the_gpu_is_busy(pipe_cfg, tmp_path) -> None:
    now = datetime(2026, 10, 24, 1, 0).timestamp()
    ran, retries = [], []
    decision = nightly_tick(now, pipe_cfg.nightly, 9.0, lambda: ran.append(1), retries.append,
                            tmp_path)  # fmt: skip
    assert decision is Decision.RETRY and ran == []
    assert retries == [now + pipe_cfg.nightly.retry_minutes * 60]


def test_a_night_lost_to_a_busy_gpu_is_reported(pipe_cfg, tmp_path) -> None:
    now = datetime(2026, 10, 24, 5, 50).timestamp()
    nightly_tick(now, pipe_cfg.nightly, 9.0, lambda: None, lambda at: None, tmp_path)
    text = next((tmp_path / "nightly").glob("*.md")).read_text(encoding="utf-8")
    assert "GPU busy" in text and "did not run" in text
