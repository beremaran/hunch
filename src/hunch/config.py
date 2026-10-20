"""Tunable parameters, loaded read-only from config/hunch.toml.

Secrets and machine-specific paths live in .env instead. Nothing here writes files.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from hunch.memory.schema import CUE_TYPES
from hunch.recall.activation import ActivationParams

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "hunch.toml"


class ConfigError(ValueError):
    pass


def _positive_int(section: str, name: str, value: object) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ConfigError(f"{section}.{name} must be a positive integer, got {value!r}")


@dataclass(frozen=True, slots=True)
class WorkingMemoryConfig:
    max_turns: int
    max_tokens: int

    def __post_init__(self) -> None:
        for name in ("max_turns", "max_tokens"):
            _positive_int("working_memory", name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class MemoryConfig:
    db_name: str


@dataclass(frozen=True, slots=True)
class EmbeddingConfig:
    model_id: str
    device: str
    dim: int
    query_instruction: str

    def __post_init__(self) -> None:
        _positive_int("embedding", "dim", self.dim)


@dataclass(frozen=True, slots=True)
class RecallConfig:
    max_upper_per_turn: int
    involuntary_per_session: int
    reconsolidation_rate: float

    def __post_init__(self) -> None:
        _positive_int("recall", "max_upper_per_turn", self.max_upper_per_turn)
        n = self.involuntary_per_session
        if not isinstance(n, int) or isinstance(n, bool) or n < 0:
            raise ConfigError(f"recall.involuntary_per_session must be an integer >= 0, got {n!r}")
        r = self.reconsolidation_rate
        if not isinstance(r, int | float) or isinstance(r, bool) or not 0 <= r <= 1:
            raise ConfigError(f"recall.reconsolidation_rate must be in [0, 1], got {r!r}")


@dataclass(frozen=True, slots=True)
class Config:
    working_memory: WorkingMemoryConfig
    memory: MemoryConfig
    embedding: EmbeddingConfig
    recall: RecallConfig
    activation: ActivationParams


def _section(data: dict, name: str, cls: type, nested: tuple[str, ...] = ()) -> dict:
    raw = data.get(name)
    if not isinstance(raw, dict):
        raise ConfigError(f"missing [{name}] section")
    expected = set(cls.__dataclass_fields__)
    if set(raw) != expected:
        raise ConfigError(
            f"[{name}] must have exactly the keys {sorted(expected)}, got {sorted(raw)}"
        )
    for key in nested:
        if not isinstance(raw[key], dict):
            raise ConfigError(f"[{name}.{key}] must be a table")
    return raw


def _activation(data: dict) -> ActivationParams:
    raw = dict(_section(data, "activation", ActivationParams, nested=("cue_type_weights",)))
    weights = raw.pop("cue_type_weights")
    rehearsal = raw.pop("rehearsal")
    if set(weights) != set(CUE_TYPES):
        raise ConfigError(f"[activation.cue_type_weights] must cover exactly {list(CUE_TYPES)}")
    for key, value in raw.items():
        if not isinstance(value, int | float) or isinstance(value, bool):
            raise ConfigError(f"activation.{key} must be a number, got {value!r}")
    try:
        return ActivationParams(
            cue_type_weights=MappingProxyType({k: float(v) for k, v in weights.items()}),
            rehearsal=rehearsal,
            **{k: float(v) for k, v in raw.items()},
        )
    except ValueError as exc:
        raise ConfigError(f"[activation]: {exc}") from exc


def load_config(path: Path = DEFAULT_CONFIG) -> Config:
    with path.open("rb") as f:
        data = tomllib.load(f)
    return Config(
        working_memory=WorkingMemoryConfig(**_section(data, "working_memory", WorkingMemoryConfig)),
        memory=MemoryConfig(**_section(data, "memory", MemoryConfig)),
        embedding=EmbeddingConfig(**_section(data, "embedding", EmbeddingConfig)),
        recall=RecallConfig(**_section(data, "recall", RecallConfig)),
        activation=_activation(data),
    )
