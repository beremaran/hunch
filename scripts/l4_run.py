"""Run the Phase-end GPU sweep as steps, with a status file you can read while it runs.

    python -m scripts.l4_run run       # runs the steps in order, one at a time
    python -m scripts.l4_run status    # prints step states, elapsed time, latest test lines

The state lives in logs/l4_status.json; each step writes its full output to its own log file.
When every step ends, Windows plays a short sound.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"
STATUS = LOGS / "l4_status.json"
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
TAG = "phase5"

STEPS: list[dict[str, Any]] = [
    {
        "name": "golden",
        "cmd": [
            PY,
            "-m",
            "pytest",
            "-m",
            "golden",
            "-v",
            "--durations=0",
            "-p",
            "no:cacheprovider",
        ],
        "log": LOGS / f"{TAG}_l4_golden_full.log",
    },
    {
        "name": "eval",
        "cmd": [PY, "-m", "eval.run_eval", "--tag", TAG, "--pipeline"],
        "log": LOGS / f"{TAG}_l4_eval.log",
    },
    {
        "name": "compare",
        "cmd": [PY, "-m", "eval.compare", "phase4", TAG],
        "log": LOGS / f"{TAG}_l4_compare.log",
    },
    {
        "name": "probes",
        "cmd": [PY, "-m", "scripts.hunch_probes", "--runs", "8"],
        "log": LOGS / f"{TAG}_l4_probes.log",
    },
]


def _now() -> float:
    return time.time()


def _write(state: dict[str, Any]) -> None:
    STATUS.parent.mkdir(exist_ok=True)
    tmp = STATUS.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(STATUS)  # atomic: status reads never see half a file


def run(names: list[str]) -> int:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    steps = [s for s in STEPS if s["name"] in names]
    state: dict[str, Any] = {
        "started": _now(),
        "steps": [{"name": s["name"], "state": "pending", "log": str(s["log"])} for s in steps],
    }
    _write(state)
    worst = 0
    for step, rec in zip(steps, state["steps"], strict=True):
        rec.update(state="running", started=_now(), pid=None)
        _write(state)
        with step["log"].open("w", encoding="utf-8") as log:
            proc = subprocess.Popen(
                step["cmd"], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT
            )
            rec["pid"] = proc.pid
            _write(state)
            code = proc.wait()
        rec.update(state="done" if code == 0 else "failed", ended=_now(), exit=code)
        _write(state)
        worst = max(worst, code)
    state["ended"] = _now()
    _write(state)
    _sound()
    return worst


def _sound() -> None:
    if sys.platform != "win32":
        return
    import winsound

    winsound.MessageBeep(winsound.MB_ICONASTERISK)


def _fmt(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}m{s:02d}s"


def _latest_lines(path: Path, n: int = 3) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return [ln for ln in lines if ln.strip()][-n:]


def status() -> int:
    sys.stdout.reconfigure(errors="replace")  # the Windows console may be cp1252
    if not STATUS.exists():
        print("No run recorded yet (logs/l4_status.json is missing).")
        return 1
    state = json.loads(STATUS.read_text(encoding="utf-8"))
    end = state.get("ended", _now())
    print(
        f"run started {time.strftime('%H:%M:%S', time.localtime(state['started']))}, "
        f"elapsed {_fmt(end - state['started'])}"
    )
    for rec in state["steps"]:
        name, st = rec["name"], rec["state"]
        if st == "pending":
            print(f"  {name:<8} pending")
            continue
        dur = rec.get("ended", _now()) - rec["started"]
        extra = f" exit={rec['exit']}" if "exit" in rec else ""
        print(f"  {name:<8} {st:<8} {_fmt(dur)}{extra}")
        if st == "running":
            log = Path(rec["log"])
            text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
            done = sum(text.count(f" {w}") for w in ("PASSED", "FAILED", "ERROR"))
            print(f"           cases finished: {done}")
            for ln in _latest_lines(log):
                print(f"           | {ln[:150]}")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "run":
        names = sys.argv[2].split(",") if len(sys.argv) > 2 else [s["name"] for s in STEPS]
        raise SystemExit(run(names))
    if cmd == "status":
        raise SystemExit(status())
    raise SystemExit("usage: python -m scripts.l4_run [run|status]")
