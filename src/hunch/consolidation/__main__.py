"""Run the nightly consolidation by hand while the bot is down (Phase 7). Loads the model, so the
GPU must be free: do not run it while the bot runs (the bot holds the model and does this itself).

    python -m hunch.consolidation [--no-golden]
"""

from __future__ import annotations

import argparse
import time

from hunch.channels.store import ChannelStore
from hunch.consolidation.golden import run_golden
from hunch.consolidation.nightly import Night, run_night
from hunch.loops.learning import DAY
from hunch.runtime import build_runtime, env_dir, load_env


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="python -m hunch.consolidation")
    p.add_argument("--no-golden", action="store_true", help="skip step 8 (no rollback check)")
    args = p.parse_args(argv)
    load_env()
    rt = build_runtime()
    now = time.time()
    golden = None if args.no_golden else (lambda: run_golden(rt.model, rt.pipeline.embedder))
    data_dir, log_dir = env_dir("HUNCH_DATA_DIR", "data"), env_dir("HUNCH_LOG_DIR", "logs")
    channels = ChannelStore(rt.pipeline.store.db)
    night = Night(rt.pipeline, channels, rt.cfg, now - DAY, now, data_dir, log_dir, golden)
    report = run_night(night)
    print(f"{'ok' if report.ok else 'rolled back'}: {report.steps}")


if __name__ == "__main__":
    main()
