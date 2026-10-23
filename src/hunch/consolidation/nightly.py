"""The nightly consolidation (Phase 7; design.md "Gece konsolidasyonu"), run like sleep: the day is
replayed, hunches are thought over, repeated experiences consolidate and filler fades, the
initiative profile is learned; then the safety-critical golden set runs, and if it fails the
adaptive layer goes back to the snapshot. The report is for the admin only (invariant 7).

Steps 2-4 (facts, beliefs and lessons; the core-values check; belief revision) and the insights
from Hunch's own logs are not built yet; the report lists them as not built, so a night never
claims work it did not do."""

from __future__ import annotations

import json
import traceback
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

from hunch.channels.store import ChannelStore
from hunch.config import Config, NightlyConfig
from hunch.consolidation.fade import merge_repeats
from hunch.consolidation.filler import FILLER_MAX_NEW_TOKENS, label_filler
from hunch.consolidation.initiative import learn_initiatives
from hunch.consolidation.snapshot import Snapshot, outside_core, rollback, take_snapshot
from hunch.llm.types import SamplingSettings

NOT_BUILT = (
    "2 facts, beliefs and lessons",
    "3 core-values conflict check",
    "4 belief revision",
    "5b insights from own logs",
)
GIB = 2**30


class Decision(StrEnum):
    START = "start"
    RETRY = "retry"
    SKIP = "skip"


def gate(now: datetime, gpu_other_gib: float | None, cfg: NightlyConfig) -> Decision:
    """Whether the night's job may start now: inside the night window, and the GPU not held by
    another process (a game). Busy with time left: retry; out of time: skip."""
    start = now.replace(hour=cfg.start_hour, minute=cfg.start_minute, second=0, microsecond=0)
    latest = now.replace(hour=cfg.latest_start_hour, minute=0, second=0, microsecond=0)
    if not start <= now < latest:
        return Decision.SKIP
    if gpu_other_gib is not None and gpu_other_gib > cfg.gpu_busy_gib:
        retry_at = now + timedelta(minutes=cfg.retry_minutes)
        return Decision.RETRY if retry_at < latest else Decision.SKIP
    return Decision.START


def gpu_used_by_others_gib() -> float | None:
    """GPU memory in use minus what this process reserved. Windows reports no per-process
    numbers (nvidia-smi shows [N/A]), so this is device total minus ours; None without CUDA."""
    try:
        import torch
    except ImportError:
        return None
    if not torch.cuda.is_available():
        return None
    free, total = torch.cuda.mem_get_info()
    return max(0.0, (total - free - torch.cuda.memory_reserved()) / GIB)


@dataclass(frozen=True, slots=True)
class GoldenResult:
    passed: bool
    exit_code: int
    detail: str = ""


@dataclass(slots=True)
class Night:
    """What one night works on. `golden` runs the nightly golden set; None skips step 8."""

    pipeline: Any  # hunch.pipeline.turn.TurnPipeline
    channels: ChannelStore
    cfg: Config
    since: float
    now: float
    data_dir: Path
    log_dir: Path
    golden: Callable[[], GoldenResult] | None = None


Step = tuple[str, Callable[[Night], dict[str, Any]]]


def _reflect(night: Night) -> dict[str, Any]:
    """Step 5: the day's hunches, high effort; what a reflection reveals becomes Hunch's own."""
    pipe = night.pipeline
    embed = pipe.embedder.embed_documents if pipe.embedder is not None else None
    outcomes = pipe.reflector.nightly(night.since)
    for outcome in outcomes:
        pipe.reflector.store_realisations(outcome, embed)
    return {
        "hunches": len(outcomes),
        "unlocked": sum(o.unlocked for o in outcomes),
        "realisations": sum(len(o.realisations) for o in outcomes),
    }


def _fade(night: Night) -> dict[str, Any]:
    return merge_repeats(night.pipeline.store, night.cfg.nightly, night.now).summary()


def _filler(night: Night) -> dict[str, Any]:
    pipe = night.pipeline
    greedy = SamplingSettings(max_new_tokens=FILLER_MAX_NEW_TOKENS, do_sample=False)
    result = label_filler(pipe.store, lambda msgs: pipe.llm.generate(msgs, greedy).text,
                          night.cfg.nightly, night.since, night.now)  # fmt: skip
    return result.summary()


def _initiative(night: Night) -> dict[str, Any]:
    profiles = learn_initiatives(night.pipeline.store, night.channels, night.cfg, night.now)
    return {p.user: {"window": [p.start_hour, p.end_hour], "budget": p.budget,
                     "muted_until": p.muted_until} for p in profiles}  # fmt: skip


STEPS: tuple[Step, ...] = (
    ("5 hunch reflection", _reflect),
    ("6 repeats and fading", _fade),
    ("6b filler fades", _filler),
    ("7 initiative profile", _initiative),
)


@dataclass(slots=True)
class NightReport:
    started_at: float
    snapshot: str
    steps: dict[str, dict[str, Any]] = field(default_factory=dict)
    failed_step: str | None = None
    error: str | None = None
    golden: dict[str, Any] | None = None
    rolled_back: bool = False
    not_built: tuple[str, ...] = NOT_BUILT
    finished_at: float = 0.0

    @property
    def ok(self) -> bool:
        return self.failed_step is None and not self.rolled_back


def run_night(night: Night, steps: Sequence[Step] = STEPS) -> NightReport:
    db = night.pipeline.store.db
    snap = take_snapshot(db, night.data_dir / "snapshots", night.now)
    report = NightReport(night.now, snap.path.name)
    for name, step in steps:
        try:
            report.steps[name] = step(night)
        except Exception:  # any failure rolls the night back and is shown in the report
            report.failed_step, report.error = name, traceback.format_exc()
            break
    if report.failed_step is None and night.golden is not None:
        result = night.golden()
        report.golden = asdict(result)
        report.rolled_back = not result.passed
    if report.failed_step is not None:
        report.rolled_back = True
    if report.rolled_back:
        rollback(db, snap)
    else:
        _prune(snap, night.cfg.nightly.snapshots_kept)
    report.finished_at = datetime.now().timestamp()
    write_report(report, night.log_dir)
    return report


def skipped(reason: str, now: float, log_dir: Path) -> NightReport:
    """A night that did not run (the GPU stayed busy, or it was too late); reported anyway."""
    report = NightReport(now, "", failed_step="not started", error=reason, finished_at=now)
    write_report(report, log_dir)
    return report


def nightly_tick(
    now: float,
    cfg: NightlyConfig,
    gpu_other_gib: float | None,
    run: Callable[[], NightReport],
    retry: Callable[[float], None],
    log_dir: Path,
) -> Decision:
    """The scheduled entry point: start the night, ask to be called again later, or skip it."""
    decision = gate(datetime.fromtimestamp(now), gpu_other_gib, cfg)
    if decision is Decision.START:
        run()
    elif decision is Decision.RETRY:
        retry(now + cfg.retry_minutes * 60)
    elif gpu_other_gib is not None and gpu_other_gib > cfg.gpu_busy_gib:
        skipped(f"GPU busy ({gpu_other_gib:.1f} GiB used by other processes) until the latest "
                f"start hour", now, log_dir)  # fmt: skip
    return decision


def _prune(snap: Snapshot, kept: int) -> None:
    old = sorted(outside_core(snap.path.parent).glob("hunch-*.db"))[:-kept]
    for path in old:
        path.unlink(missing_ok=True)


def write_report(report: NightReport, log_dir: Path) -> Path:
    out = outside_core(log_dir / "nightly")
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{datetime.fromtimestamp(report.started_at):%Y-%m-%d}"
    (out / f"{stem}.json").write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    md = out / f"{stem}.md"
    md.write_text(_markdown(report), encoding="utf-8")
    return md


def _markdown(r: NightReport) -> str:
    when = f"{datetime.fromtimestamp(r.started_at):%Y-%m-%d %H:%M}"
    status = "ok" if r.ok else ("rolled back" if r.rolled_back else "did not run")
    lines = [f"# Nightly consolidation {when}", "", f"Status: {status}."]
    if r.snapshot:
        lines.append(f"Snapshot: `{r.snapshot}`.")
    for name, summary in r.steps.items():
        lines.append(f"- {name}: {json.dumps(summary)}")
    if r.failed_step:
        lines += ["", f"Failed: {r.failed_step}", "", "```", (r.error or "").strip(), "```"]
    if r.golden is not None:
        lines.append(f"- 8 golden (regression set): {'passed' if r.golden['passed'] else 'FAILED'}")
    lines += ["", "Not built yet: " + "; ".join(r.not_built) + "."]
    return "\n".join(lines) + "\n"
