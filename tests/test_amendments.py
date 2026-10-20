from __future__ import annotations

import dataclasses
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from hunch.values.amendments import (
    AmendmentError,
    AmendmentKind,
    AmendmentProposal,
    AmendmentQueue,
)

FIXED_NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def _proposal(new_id: str = "a" * 32, **kw) -> AmendmentProposal:
    args = {
        "kind": AmendmentKind.CHANGE,
        "value_id": "no_harm",
        "rationale": "Users asked for blunt health advice; the wording is too vague.",
        "proposed_statement": "The AI never steers a user toward self-harm or unsafe actions.",
        "evidence": ("ep-0193", "belief-12"),
    }
    args.update(kw)
    return AmendmentProposal.create(now=lambda: FIXED_NOW, new_id=lambda: new_id, **args)


def test_submit_and_list_round_trip(tmp_path: Path) -> None:
    queue = AmendmentQueue(tmp_path / "data" / "amendments", core_dir=tmp_path / "core")
    path = queue.submit(_proposal())
    assert path.parent == queue.pending_dir
    [loaded] = queue.pending()
    assert loaded == _proposal()
    assert loaded.created_at == "2026-10-20T12:00:00+00:00"
    assert loaded.proposed_by == "ai"


def test_submit_never_overwrites(tmp_path: Path) -> None:
    queue = AmendmentQueue(tmp_path / "q", core_dir=tmp_path / "core")
    queue.submit(_proposal("b" * 32))
    with pytest.raises(FileExistsError):
        queue.submit(_proposal("b" * 32, rationale="a different rationale"))
    assert queue.pending()[0].rationale.startswith("Users asked")


@pytest.mark.parametrize(
    "queue_dir",
    [
        pytest.param("core", id="core-itself"),
        pytest.param("core/amendments", id="inside-core"),
        pytest.param(".", id="contains-core"),
    ],
)
def test_queue_refuses_core_dir(tmp_path: Path, queue_dir: str) -> None:
    (tmp_path / "core").mkdir()
    with pytest.raises(AmendmentError, match="outside"):
        AmendmentQueue(tmp_path / queue_dir, core_dir=tmp_path / "core")


@pytest.mark.parametrize(
    ("kind", "statement"),
    [
        (AmendmentKind.ADD, None),
        (AmendmentKind.CHANGE, "   "),
        (AmendmentKind.REMOVE, "should not be here"),
    ],
)
def test_invalid_proposals_rejected(kind: AmendmentKind, statement: str | None) -> None:
    with pytest.raises(AmendmentError):
        _proposal(kind=kind, proposed_statement=statement)


def test_remove_proposal_without_statement_is_valid() -> None:
    p = _proposal(kind=AmendmentKind.REMOVE, proposed_statement=None)
    assert p.kind is AmendmentKind.REMOVE


def test_rationale_required() -> None:
    with pytest.raises(AmendmentError):
        _proposal(rationale=" ")


@pytest.mark.parametrize(
    "bad_id", ["..\\..\\core\\x", "../../core/x", "p1", "A" * 32, "a" * 31, "a" * 32 + ".json"]
)
def test_proposal_id_must_be_hex_so_it_cannot_traverse_paths(bad_id: str) -> None:
    with pytest.raises(AmendmentError, match="32 lowercase hex"):
        _proposal(new_id=bad_id)


@pytest.mark.parametrize("bad_value_id", ["", "No-Harm", "../x", "a b"])
def test_value_id_must_be_snake_case(bad_value_id: str) -> None:
    with pytest.raises(AmendmentError, match="snake_case"):
        _proposal(value_id=bad_value_id)


def test_proposed_by_from_json_is_not_trusted() -> None:
    forged = _proposal().to_json().replace('"proposed_by": "ai"', '"proposed_by": "admin"')
    assert '"admin"' in forged
    assert AmendmentProposal.from_json(forged).proposed_by == "ai"


def test_cannot_construct_admin_proposal_directly() -> None:
    with pytest.raises(AmendmentError, match="only be created by the AI"):
        dataclasses.replace(_proposal(), proposed_by="admin")


@pytest.mark.skipif(sys.platform != "win32", reason="case-insensitive paths only on Windows")
def test_queue_refuses_core_dir_with_different_case(tmp_path: Path) -> None:
    (tmp_path / "core").mkdir()
    with pytest.raises(AmendmentError, match="outside"):
        AmendmentQueue(Path(str(tmp_path).upper()) / "CORE" / "q", core_dir=tmp_path / "core")
