"""Turn log (design.md, "Gözlemlenebilirlik"): one JSON line per turn, for the admin only.

turns.jsonl has exactly the fields of the design.md example, in that order. Everything else the
admin needs to follow a turn (candidate texts, filter reasons, judge output, per-stage latency,
peak VRAM) goes to turn_details.jsonl under the same turn_id. Logs are never fed back to the AI
(invariant 7): nothing in the pipeline reads these files. reflections.jsonl (Phase 4) is the
reflection log and disclosures.jsonl (Phase 5) the disclosure log, written the same way.

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
REFLECTIONS_FILE = "reflections.jsonl"
DISCLOSURES_FILE = "disclosures.jsonl"


class TurnLogError(RuntimeError):
    pass


def _is_within(path: Path, parent: Path) -> bool:
    path, parent = Path(os.path.normcase(path)), Path(os.path.normcase(parent))
    return path == parent or parent in path.parents


class _JsonlLog:
    """Append-only JSON lines in one directory outside core/."""

    def __init__(self, log_dir: Path | str, core_dir: Path) -> None:
        self.dir = Path(log_dir).resolve()
        self.core_dir = Path(core_dir)
        if _is_within(self.dir, core_dir.resolve()):
            raise TurnLogError(f"log dir {self.dir} must be outside the core values dir")
        self.dir.mkdir(parents=True, exist_ok=True)

    def _append(self, name: str, record: dict[str, Any]) -> None:
        path = self.dir / name
        if path.suffix != ".jsonl" or path.parent != self.dir:
            raise TurnLogError(f"logs may only append to .jsonl files in {self.dir}")
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


class TurnLog(_JsonlLog):
    def write(self, turn: dict[str, Any], details: dict[str, Any]) -> None:
        if tuple(turn) != TURN_LOG_FIELDS:
            raise TurnLogError(
                f"turn record must have exactly {TURN_LOG_FIELDS}, got {tuple(turn)}"
            )
        self._append(TURNS_FILE, turn)
        self._append(DETAILS_FILE, {"turn_id": turn["turn_id"], **details})


class ReflectionLog(_JsonlLog):
    """design.md "Yansıtma logu": which hunch, which level it reached, the source, attempts and
    probabilities, the verdict and what it changed. Admin only: nothing reads it back and none of
    it reaches a prompt (invariants 2 and 7)."""

    def write(self, record: dict[str, Any]) -> None:
        if "reflection_id" not in record or "hunch_id" not in record:
            raise TurnLogError("reflection record needs reflection_id and hunch_id")
        self._append(REFLECTIONS_FILE, record)


class DisclosureLog(_JsonlLog):
    """design.md "İfşa logu" (Phase 5): every candidate the disclosure gate blocked, why (rule or
    judge), which other users' memories it touched, and the judge's raw answer. Admin only."""

    def write(self, record: dict[str, Any]) -> None:
        if "turn_id" not in record or "candidate" not in record:
            raise TurnLogError("disclosure record needs turn_id and candidate")
        self._append(DISCLOSURES_FILE, record)
