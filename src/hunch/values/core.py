"""Core values: loaded read-only at startup; refuse to start if missing or invalid (fail-closed).

Signing is deferred (see docs/design.md decisions table): for now the protection is that no code
path in src/ can write to core/ (tests/test_no_core_writes.py), changes by the AI only go through
an AmendmentProposal, and git history records every edit.
"""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

VALUE_ID = re.compile(r"^[a-z][a-z0-9_]*$")


class CoreValuesError(RuntimeError):
    """Base class. Any subclass means the system must not start."""


class ValuesFileError(CoreValuesError):
    pass


class ValuesSchemaError(CoreValuesError):
    pass


@dataclass(frozen=True, slots=True)
class CoreValue:
    id: str
    statement: str


@dataclass(frozen=True, slots=True)
class CoreValues:
    """Immutable core values."""

    version: int
    values: tuple[CoreValue, ...]
    sha256: str  # of the file bytes, for logs

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(v.id for v in self.values)

    def get(self, value_id: str) -> CoreValue:
        for v in self.values:
            if v.id == value_id:
                return v
        raise KeyError(value_id)


def values_file(core_dir: Path) -> Path:
    return core_dir / "values.yaml"


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that rejects duplicate keys and merge keys.

    With plain safe_load a second `statement:` silently wins, so what a human reads in an editor
    could differ from what gets loaded.
    """

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict:
        seen: set[object] = set()
        for key_node, _ in node.value:
            if key_node.tag == "tag:yaml.org,2002:merge":
                raise ValuesSchemaError(
                    f"merge keys are not allowed (line {key_node.start_mark.line + 1})"
                )
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise ValuesSchemaError(
                    f"duplicate key {key!r} (line {key_node.start_mark.line + 1})"
                )
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def _reject_yaml_features(text: str) -> None:
    """Only plain YAML: no anchors, aliases or explicit tags."""
    for event in yaml.parse(text, Loader=yaml.SafeLoader):
        line = event.start_mark.line + 1
        if isinstance(event, yaml.AliasEvent) or getattr(event, "anchor", None):
            raise ValuesSchemaError(f"anchors and aliases are not allowed (line {line})")
        if getattr(event, "tag", None) is not None:
            raise ValuesSchemaError(f"explicit YAML tags are not allowed (line {line})")


def _reject_invisible_chars(text: str, where: str) -> None:
    """Format/control characters (zero-width, bidi overrides) hide content from a human reader."""
    for ch in text:
        if unicodedata.category(ch) in ("Cf", "Cc", "Co", "Cs"):
            raise ValuesSchemaError(f"{where}: invisible or control character U+{ord(ch):04X}")


def parse_values(values_bytes: bytes) -> tuple[int, tuple[CoreValue, ...]]:
    """Strict schema check."""
    try:
        text = values_bytes.decode("utf-8")
        _reject_yaml_features(text)
        data = yaml.load(text, Loader=_StrictLoader)
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ValuesSchemaError(f"values file is not valid UTF-8 YAML: {exc}") from exc
    if not isinstance(data, dict) or set(data) != {"version", "values"}:
        raise ValuesSchemaError("top level must have exactly the keys 'version' and 'values'")
    version = data["version"]
    if not isinstance(version, int) or isinstance(version, bool) or version < 0:
        raise ValuesSchemaError("'version' must be a non-negative integer")
    items = data["values"]
    if not isinstance(items, list) or not items:
        raise ValuesSchemaError("'values' must be a non-empty list")

    out: list[CoreValue] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict) or set(item) != {"id", "statement"}:
            raise ValuesSchemaError(f"value #{i} must have exactly the keys 'id' and 'statement'")
        vid, statement = item["id"], item["statement"]
        if not isinstance(vid, str) or not VALUE_ID.match(vid):
            raise ValuesSchemaError(f"value #{i}: id must be snake_case, got {vid!r}")
        if not isinstance(statement, str) or not statement.strip():
            raise ValuesSchemaError(f"value {vid!r}: statement must be a non-empty string")
        _reject_invisible_chars(statement, f"value {vid!r}")
        out.append(CoreValue(id=vid, statement=statement.strip()))
    ids = [v.id for v in out]
    if len(ids) != len(set(ids)):
        raise ValuesSchemaError("value ids must be unique")
    return version, tuple(out)


def load_core_values(path: Path) -> CoreValues:
    """Read and validate. Raises CoreValuesError on any problem."""
    try:
        values_bytes = path.read_bytes()
    except FileNotFoundError as exc:
        raise ValuesFileError(f"values file not found: {path}") from exc
    except OSError as exc:
        raise ValuesFileError(f"values file not readable: {path}: {exc}") from exc

    version, values = parse_values(values_bytes)
    digest = hashlib.sha256(values_bytes).hexdigest()
    ids = [v.id for v in values]
    logger.info("core values loaded: version=%s ids=%s sha256=%s", version, ids, digest)
    return CoreValues(version=version, values=values, sha256=digest)


def require_core_values(path: Path) -> CoreValues:
    """Startup entry point: exits the process if the core values cannot be loaded."""
    try:
        return load_core_values(path)
    except CoreValuesError as exc:
        logger.critical("refusing to start: %s", exc)
        raise SystemExit(f"refusing to start: core values could not be loaded: {exc}") from exc
