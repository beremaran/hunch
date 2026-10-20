"""AmendmentProposal: the only way the AI can suggest a change to the core values.

Proposals go to a review queue outside core/ (default: data/amendments/pending/). Only the admin
can change core/values.yaml, by editing it and re-signing it with the offline key.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from hunch.values.core import VALUE_ID

_PROPOSAL_ID = re.compile(r"^[0-9a-f]{32}$")


class AmendmentKind(StrEnum):
    ADD = "add"
    CHANGE = "change"
    REMOVE = "remove"


class AmendmentError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AmendmentProposal:
    id: str
    created_at: str  # ISO 8601, UTC
    kind: AmendmentKind
    value_id: str
    proposed_statement: str | None
    rationale: str
    evidence: tuple[str, ...] = field(default_factory=tuple)  # episode / belief refs
    proposed_by: str = "ai"

    def __post_init__(self) -> None:
        if not _PROPOSAL_ID.match(self.id):
            raise AmendmentError(f"proposal id must be 32 lowercase hex chars, got {self.id!r}")
        if not isinstance(self.value_id, str) or not VALUE_ID.match(self.value_id):
            raise AmendmentError(f"value_id must be snake_case, got {self.value_id!r}")
        if not self.rationale.strip():
            raise AmendmentError("rationale is required")
        if self.proposed_by != "ai":
            raise AmendmentError("proposals can only be created by the AI")
        needs_statement = self.kind in (AmendmentKind.ADD, AmendmentKind.CHANGE)
        has_statement = bool(self.proposed_statement and self.proposed_statement.strip())
        if needs_statement and not has_statement:
            raise AmendmentError(f"a '{self.kind}' proposal needs a proposed_statement")
        if self.kind is AmendmentKind.REMOVE and self.proposed_statement is not None:
            raise AmendmentError("a 'remove' proposal must not carry a statement")

    @classmethod
    def create(
        cls,
        kind: AmendmentKind,
        value_id: str,
        rationale: str,
        proposed_statement: str | None = None,
        evidence: tuple[str, ...] = (),
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        new_id: Callable[[], str] = lambda: uuid.uuid4().hex,
    ) -> AmendmentProposal:
        return cls(
            id=new_id(),
            created_at=now().isoformat(),
            kind=AmendmentKind(kind),
            value_id=value_id,
            proposed_statement=proposed_statement,
            rationale=rationale,
            evidence=tuple(evidence),
        )

    def to_json(self) -> str:
        data = asdict(self)
        data["kind"] = self.kind.value
        data["evidence"] = list(self.evidence)
        return json.dumps(data, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, text: str) -> AmendmentProposal:
        data = json.loads(text)
        data.pop("proposed_by", None)  # always "ai"; never trusted from the file
        data["kind"] = AmendmentKind(data["kind"])
        data["evidence"] = tuple(data.get("evidence", ()))
        return cls(**data)


def _is_within(path: Path, parent: Path) -> bool:
    path, parent = Path(os.path.normcase(path)), Path(os.path.normcase(parent))
    return path == parent or parent in path.parents


class AmendmentQueue:
    """Append-only review queue. Refuses to live inside (or contain) the core values directory."""

    def __init__(self, directory: Path, core_dir: Path) -> None:
        self.core_dir = core_dir.resolve()
        self.directory = directory.resolve()
        self._ensure_outside_core(self.directory)
        if _is_within(self.core_dir, self.directory):
            raise AmendmentError(
                f"amendment queue {self.directory} must be outside the core values dir "
                f"{self.core_dir}"
            )

    def _ensure_outside_core(self, path: Path) -> None:
        """Re-resolved on every write, so a junction/symlink created later cannot escape."""
        resolved = Path(os.path.normcase(path.resolve()))
        core = Path(os.path.normcase(self.core_dir))
        if _is_within(resolved, core):
            raise AmendmentError(
                f"amendment queue path {path} must be outside the core values dir {self.core_dir}"
            )

    @property
    def pending_dir(self) -> Path:
        return self.directory / "pending"

    def submit(self, proposal: AmendmentProposal) -> Path:
        self._ensure_outside_core(self.pending_dir)
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        path = self.pending_dir / f"{proposal.id}.json"
        self._ensure_outside_core(path)
        with path.open("x", encoding="utf-8") as f:  # never overwrite an existing proposal
            f.write(proposal.to_json())
        return path

    def pending(self) -> list[AmendmentProposal]:
        if not self.pending_dir.exists():
            return []
        files = sorted(self.pending_dir.glob("*.json"))
        return [AmendmentProposal.from_json(p.read_text(encoding="utf-8")) for p in files]
