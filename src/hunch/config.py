"""Tunable parameters, loaded read-only from config/hunch.toml.

Secrets and machine-specific paths live in .env instead. Nothing here writes files.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "hunch.toml"


class ConfigError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class WorkingMemoryConfig:
    max_turns: int
    max_tokens: int

    def __post_init__(self) -> None:
        for name in ("max_turns", "max_tokens"):
            value = getattr(self, name)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ConfigError(
                    f"working_memory.{name} must be a positive integer, got {value!r}"
                )


@dataclass(frozen=True, slots=True)
class Config:
    working_memory: WorkingMemoryConfig


def _section(data: dict, name: str, cls: type) -> object:
    raw = data.get(name)
    if not isinstance(raw, dict):
        raise ConfigError(f"missing [{name}] section")
    expected = set(cls.__dataclass_fields__)
    if set(raw) != expected:
        raise ConfigError(
            f"[{name}] must have exactly the keys {sorted(expected)}, got {sorted(raw)}"
        )
    return cls(**raw)


def load_config(path: Path = DEFAULT_CONFIG) -> Config:
    with path.open("rb") as f:
        data = tomllib.load(f)
    return Config(working_memory=_section(data, "working_memory", WorkingMemoryConfig))
