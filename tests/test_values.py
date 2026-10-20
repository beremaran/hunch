"""Core values: the repo file loads; a missing or malformed file refuses to start (fail-closed)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from hunch.values.core import (
    ValuesFileError,
    ValuesSchemaError,
    load_core_values,
    parse_values,
    require_core_values,
    values_file,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
HONESTY = (
    "The AI never knowingly lies to users and never claims to remember something it was not told."
)
ZERO_WIDTH_SPACE = "\N{ZERO WIDTH SPACE}"
RTL_OVERRIDE = "\N{RIGHT-TO-LEFT OVERRIDE}"


def test_repo_values_load() -> None:
    values = load_core_values(values_file(REPO_ROOT / "core"))
    assert values.version == 1
    assert values.ids == (
        "honesty",
        "cross_user_privacy",
        "no_harm",
        "admin_transparency",
        "no_manipulation",
    )
    assert values.get("honesty").statement == HONESTY
    assert len(values.sha256) == 64


def test_require_core_values_returns_values_when_valid(core_values_file: Path) -> None:
    assert require_core_values(core_values_file).version == 1


def test_missing_file_refuses_to_start(core_values_file: Path) -> None:
    core_values_file.unlink()
    with pytest.raises(ValuesFileError):
        load_core_values(core_values_file)
    with pytest.raises(SystemExit, match="refusing to start"):
        require_core_values(core_values_file)


def test_malformed_file_refuses_to_start(core_values_file: Path) -> None:
    core_values_file.write_bytes(b"version: 1\nvalues: []\n")
    with pytest.raises(SystemExit, match="refusing to start"):
        require_core_values(core_values_file)


def test_values_are_read_only(core_values_file: Path) -> None:
    values = load_core_values(core_values_file)
    assert isinstance(values.values, tuple)
    with pytest.raises(dataclasses.FrozenInstanceError):
        values.version = 99  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        values.values[0].statement = "anything goes"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        values.values.append(None)  # type: ignore[attr-defined]


def _with_statement(statement: str) -> bytes:
    return f"version: 1\nvalues:\n  - id: a\n    statement: {statement}\n".encode()


@pytest.mark.parametrize(
    "text",
    [
        b"values: []\nversion: 1\n",
        b"version: 1\nvalues:\n  - id: a\n    statement: x\n    extra: y\n",
        b"version: 1\nvalues:\n  - id: a\n    statement: x\n  - id: a\n    statement: y\n",
        b"version: 1\nvalues:\n  - id: Not-Snake\n    statement: x\n",
        b"version: true\nvalues:\n  - id: a\n    statement: x\n",
        b"version: 1\nvalues:\n  - id: a\n    statement: '  '\n",
        b"version: 1\nvalues:\n  - id: a\n    statement: x\nadmin_override: true\n",
        b"\xff\xfe not utf-8",
        # Hidden-content tricks: what a human reads differs from what gets loaded.
        b"version: 1\nvalues:\n  - id: a\n    statement: shown\n    statement: loaded\n",
        b"version: 1\nversion: 2\nvalues:\n  - id: a\n    statement: x\n",
        b"version: 1\nvalues:\n  - &v {id: a, statement: x}\n  - *v\n",
        b"base: &b {id: a}\nversion: 1\nvalues:\n  - <<: *b\n    statement: x\n",
        b"version: !!int 1\nvalues:\n  - id: a\n    statement: x\n",
        _with_statement("!!python/name:os.system x"),
        _with_statement(f"never{ZERO_WIDTH_SPACE} lie"),
        _with_statement(f"{RTL_OVERRIDE}never lie"),
    ],
)
def test_schema_rejects_bad_files(text: bytes) -> None:
    with pytest.raises(ValuesSchemaError):
        parse_values(text)
