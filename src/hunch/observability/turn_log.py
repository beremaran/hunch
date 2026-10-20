"""Turn log (design.md, "Gözlemlenebilirlik"): one JSON line per turn, for the admin only.

turns.jsonl has exactly the fields of the design.md example, in that order. Everything else the
admin needs to follow a turn (candidate texts, filter reasons, judge output, per-stage latency,
peak VRAM) goes to turn_details.jsonl under the same turn_id. Logs are never fed back to the AI
(invariant 7): nothing in the pipeline reads these files.

The writer only appends to .jsonl files outside core/ (tests/test_no_core_writes.py).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

TURN_LOG_FIELDS: tuple[str, ...] = (
    "turn_id", "user", "cues", "activated", "mood", "drive", "hunch", "candidates", "chosen",
    "chosen_by", "value_gate",
)  # fmt: skip
TURNS_FILE = "turns.jsonl"
DETAILS_FILE = "turn_details.jsonl"


class TurnLogError(RuntimeError):
    pass


def _is_within(path: Path, parent: Path) -> bool:
    path, parent = Path(os.path.normcase(path)), Path(os.path.normcase(parent))
    return path == parent or parent in path.parents


class TurnLog:
    def __init__(self, log_dir: Path | str, core_dir: Path) -> None:
        self.dir = Path(log_dir).resolve()
        if _is_within(self.dir, core_dir.resolve()):
            raise TurnLogError(f"log dir {self.dir} must be outside the core values dir")
        self.dir.mkdir(parents=True, exist_ok=True)

    def _append(self, name: str, record: dict[str, Any]) -> None:
        path = self.dir / name
        if path.suffix != ".jsonl" or path.parent != self.dir:
            raise TurnLogError(f"turn log may only append to .jsonl files in {self.dir}")
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def write(self, turn: dict[str, Any], details: dict[str, Any]) -> None:
        if tuple(turn) != TURN_LOG_FIELDS:
            raise TurnLogError(
                f"turn record must have exactly {TURN_LOG_FIELDS}, got {tuple(turn)}"
            )
        self._append(TURNS_FILE, turn)
        self._append(DETAILS_FILE, {"turn_id": turn["turn_id"], **details})
