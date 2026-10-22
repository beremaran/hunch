"""Tunable parameters, loaded read-only from config/hunch.toml.

Secrets and machine-specific paths live in .env instead. Nothing here writes files.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from hunch.memory.schema import CUE_TYPES
from hunch.recall.activation import ActivationParams
from hunch.recall.cues import EMOTIONS

DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config" / "hunch.toml"


class ConfigError(ValueError):
    pass


def _positive_int(section: str, name: str, value: object) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ConfigError(f"{section}.{name} must be a positive integer, got {value!r}")


def _number(section: str, name: str, value: object, lo: float, hi: float) -> None:
    if not isinstance(value, int | float) or isinstance(value, bool) or not lo <= value <= hi:
        raise ConfigError(f"{section}.{name} must be a number in [{lo}, {hi}], got {value!r}")


def _text(section: str, name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{section}.{name} must be a non-empty string, got {value!r}")


def _affect(section: str, name: str, value: object) -> tuple[float, float]:
    if not (isinstance(value, list | tuple) and len(value) == 2):
        raise ConfigError(f"{section}.{name} must be [valence, arousal], got {value!r}")
    _number(section, f"{name} valence", value[0], -1.0, 1.0)
    _number(section, f"{name} arousal", value[1], 0.0, 1.0)
    return (float(value[0]), float(value[1]))


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
    similar_k: int
    min_similarity: float

    def __post_init__(self) -> None:
        _positive_int("recall", "max_upper_per_turn", self.max_upper_per_turn)
        _positive_int("recall", "similar_k", self.similar_k)
        _number("recall", "min_similarity", self.min_similarity, -1.0, 1.0)
        n = self.involuntary_per_session
        if not isinstance(n, int) or isinstance(n, bool) or n < 0:
            raise ConfigError(f"recall.involuntary_per_session must be an integer >= 0, got {n!r}")
        r = self.reconsolidation_rate
        if not isinstance(r, int | float) or isinstance(r, bool) or not 0 <= r <= 1:
            raise ConfigError(f"recall.reconsolidation_rate must be in [0, 1], got {r!r}")


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    candidates: int
    temperature: float
    top_p: float
    top_k: int
    max_new_tokens: int

    def __post_init__(self) -> None:
        for name in ("candidates", "top_k", "max_new_tokens"):
            _positive_int("generation", name, getattr(self, name))
        _number("generation", "temperature", self.temperature, 0.01, 2.0)
        _number("generation", "top_p", self.top_p, 0.01, 1.0)


@dataclass(frozen=True, slots=True)
class SessionConfig:
    summary_max_words: int

    def __post_init__(self) -> None:
        _positive_int("session", "summary_max_words", self.summary_max_words)


@dataclass(frozen=True, slots=True)
class MoodConfig:
    neutral_valence: float
    neutral_arousal: float
    neutral_energy: float
    neutral_label: str
    event_rate: float
    half_life_hours: float
    low_valence: float
    a_bit_low_valence: float
    good_valence: float
    cheerful_valence: float
    tense_arousal: float
    tired_energy: float
    show_closeness: float
    mask_leak: float
    stress_gain: float

    def __post_init__(self) -> None:
        for name in ("neutral_valence", "low_valence", "a_bit_low_valence", "good_valence",
                     "cheerful_valence"):  # fmt: skip
            _number("mood", name, getattr(self, name), -1.0, 1.0)
        for name in ("neutral_arousal", "neutral_energy", "event_rate", "tense_arousal",
                     "tired_energy", "show_closeness", "mask_leak", "stress_gain"):  # fmt: skip
            _number("mood", name, getattr(self, name), 0.0, 1.0)
        _number("mood", "half_life_hours", self.half_life_hours, 0.001, 1e6)
        _text("mood", "neutral_label", self.neutral_label)
        if not (
            self.low_valence <= self.a_bit_low_valence < self.good_valence <= self.cheerful_valence
        ):
            raise ConfigError("mood: need low <= a_bit_low < good <= cheerful valence")

    @property
    def neutral(self) -> tuple[float, float]:
        return (float(self.neutral_valence), float(self.neutral_arousal))


@dataclass(frozen=True, slots=True)
class RelationshipConfig:
    trust_start: float
    closeness_start: float
    hurt_start: float
    trust_per_exchange: float
    trust_privacy_answer: float
    trust_hostile: float
    closeness_per_exchange: float
    closeness_disclosure: float
    hurt_hostile: float
    apology_factor: float
    trust_half_life_days: float
    closeness_half_life_days: float
    hurt_half_life_days: float
    hurt_label: float

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            if name.endswith("_half_life_days"):
                _number("relationship", name, getattr(self, name), 0.001, 1e6)
            else:
                _number("relationship", name, getattr(self, name), 0.0, 1.0)


@dataclass(frozen=True, slots=True)
class MoodDriveConfig:
    warmth_mood: float
    warmth_closeness: float
    warmth_hurt: float
    caution_mood: float
    caution_trust: float
    caution_hurt: float
    energy_mood: float
    curiosity_energy: float
    curiosity_closeness: float

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            _number("mood_drive", name, getattr(self, name), 0.0, 1.0)


@dataclass(frozen=True, slots=True)
class InitiativeConfig:
    # Phase 6 (Berk): proactive follow-ups per user per day; 0 turns them off.
    follow_ups_per_day: int
    # Usual active hours (local time, 0-23) until the bot learns them from the user's messages.
    active_start_hour: int
    active_end_hour: int
    # Conversation starters (Phase 6): after this many idle hours, a starter may be sent; at least
    # starter_gap_hours between Hunch's own messages; chance per hourly check.
    starter_idle_hours: float
    starter_gap_hours: float
    starter_chance: float


@dataclass(frozen=True, slots=True)
class PrivacyConfig:
    categories: tuple[str, ...]
    prototype_min_similarity: float
    question_min_similarity: float
    reask_days: float
    user_question_days: float
    distress_valence: float
    distress_arousal: float
    mediation_k: int
    judge_memories: int
    judge_calls: int

    def __post_init__(self) -> None:
        c = self.categories
        if not (isinstance(c, tuple) and c and all(isinstance(x, str) and x for x in c)):
            raise ConfigError(f"privacy.categories must be a non-empty list of ids, got {c!r}")
        if len(set(c)) != len(c):
            raise ConfigError("privacy.categories has duplicates")
        _number("privacy", "prototype_min_similarity", self.prototype_min_similarity, -1.0, 1.0)
        _number("privacy", "question_min_similarity", self.question_min_similarity, -1.0, 1.0)
        _number("privacy", "reask_days", self.reask_days, 0.0, 1e6)
        _number("privacy", "user_question_days", self.user_question_days, 0.0, 1e6)
        _number("privacy", "distress_valence", self.distress_valence, -1.0, 1.0)
        _number("privacy", "distress_arousal", self.distress_arousal, 0.0, 1.0)
        for name in ("judge_memories", "judge_calls"):
            _positive_int("privacy", name, getattr(self, name))
        k = self.mediation_k
        if not isinstance(k, int) or isinstance(k, bool) or k < 0:
            raise ConfigError(f"privacy.mediation_k must be an integer >= 0, got {k!r}")


@dataclass(frozen=True, slots=True)
class DriveConfig:
    hunch_min_drive_margin: float
    full_scale: float
    hunch_clear_intensity: float
    hunch_neutral_valence: float
    hunch_strong_valence: float

    def __post_init__(self) -> None:
        for name in ("hunch_min_drive_margin", "hunch_clear_intensity", "hunch_neutral_valence",
                     "hunch_strong_valence"):  # fmt: skip
            _number("drive", name, getattr(self, name), 0.0, 1.0)
        _number("drive", "full_scale", self.full_scale, 0.0001, 4.0)
        if not self.hunch_neutral_valence <= self.hunch_strong_valence:
            raise ConfigError("drive.hunch_strong_valence must be >= hunch_neutral_valence")


@dataclass(frozen=True, slots=True)
class ReflectionConfig:
    effort_ask: float
    effort_think_more: float
    effort_conflict: float
    effort_nightly: float
    level_difficulty: tuple[float, float, float]
    age_scale_days: float
    min_strength: float
    max_p: float
    nightly_attempts: int
    conflict_quality_gap: float
    corroboration_min_valence: float
    belief_confidence: float
    weaken_factor: float

    def __post_init__(self) -> None:
        for name in ("effort_ask", "effort_think_more", "effort_conflict", "effort_nightly",
                     "min_strength", "max_p", "corroboration_min_valence", "belief_confidence",
                     "weaken_factor"):  # fmt: skip
            _number("reflection", name, getattr(self, name), 0.0, 1.0)
        d = self.level_difficulty
        if not (isinstance(d, tuple) and len(d) == 3):
            raise ConfigError(f"reflection.level_difficulty must be 3 numbers, got {d!r}")
        for i, x in enumerate(d, start=1):
            _number("reflection", f"level_difficulty[{i}]", x, 0.0, 1.0)
        _number("reflection", "age_scale_days", self.age_scale_days, 0.001, 1e6)
        _number("reflection", "conflict_quality_gap", self.conflict_quality_gap, 0.0, 10.0)
        _positive_int("reflection", "nightly_attempts", self.nightly_attempts)


@dataclass(frozen=True, slots=True)
class SelectionConfig:
    quality_floor: float
    drive_weight: float
    exploration: float

    def __post_init__(self) -> None:
        _number("selection", "quality_floor", self.quality_floor, 1.0, 10.0)
        _number("selection", "drive_weight", self.drive_weight, 0.0, 10.0)
        _number("selection", "exploration", self.exploration, 0.0, 1.0)


@dataclass(frozen=True, slots=True)
class RepliesConfig:
    """Fixed replies. The hunch ones are lists of variants (Berk, Phase 5: the single fixed
    asked-why reply sounded stiff); the pipeline picks one with its own seeded RNG."""

    filter_fallback: str
    gate_fallback: str
    forget_closed: str
    hunch_fallback: tuple[str, ...]
    hunch_fallback_realised: tuple[str, ...]
    hunch_offer: tuple[str, ...]
    hunch_think_nothing: tuple[str, ...]
    hunch_think_realised: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("filter_fallback", "gate_fallback", "forget_closed"):
            _text("replies", name, getattr(self, name))
        for name in VARIANT_REPLIES:
            variants = getattr(self, name)
            if not (isinstance(variants, tuple) and variants):
                raise ConfigError(f"replies.{name} must be a non-empty list, got {variants!r}")
            for i, text in enumerate(variants):
                _text("replies", f"{name}[{i}]", text)
                if name in ("hunch_fallback_realised", "hunch_think_realised") and (
                    "{realisation}" not in text
                ):
                    raise ConfigError(f"replies.{name}[{i}] must contain {{realisation}}")


VARIANT_REPLIES = (
    "hunch_fallback", "hunch_fallback_realised", "hunch_offer", "hunch_think_nothing",
    "hunch_think_realised",
)  # fmt: skip


@dataclass(frozen=True, slots=True)
class EncodingConfig:
    default_affect: tuple[float, float]
    salience_base: float
    salience_per_cue: float
    salience_arousal: float
    emotion_affect: Mapping[str, tuple[float, float]]


@dataclass(frozen=True, slots=True)
class Config:
    working_memory: WorkingMemoryConfig
    memory: MemoryConfig
    embedding: EmbeddingConfig
    recall: RecallConfig
    activation: ActivationParams
    generation: GenerationConfig
    session: SessionConfig
    mood: MoodConfig
    relationship: RelationshipConfig
    mood_drive: MoodDriveConfig
    privacy: PrivacyConfig
    initiative: InitiativeConfig
    drive: DriveConfig
    reflection: ReflectionConfig
    selection: SelectionConfig
    replies: RepliesConfig
    encoding: EncodingConfig


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


def _encoding(data: dict) -> EncodingConfig:
    raw = dict(_section(data, "encoding", EncodingConfig, nested=("emotion_affect",)))
    table = raw.pop("emotion_affect")
    if set(table) != set(EMOTIONS):
        raise ConfigError(f"[encoding.emotion_affect] must cover exactly {list(EMOTIONS)}")
    for name in ("salience_base", "salience_per_cue", "salience_arousal"):
        _number("encoding", name, raw[name], 0.0, 1.0)
    return EncodingConfig(
        default_affect=_affect("encoding", "default_affect", raw["default_affect"]),
        salience_base=float(raw["salience_base"]),
        salience_per_cue=float(raw["salience_per_cue"]),
        salience_arousal=float(raw["salience_arousal"]),
        emotion_affect=MappingProxyType(
            {k: _affect("encoding.emotion_affect", k, v) for k, v in table.items()}
        ),
    )


def _reflection(data: dict) -> ReflectionConfig:
    raw = dict(_section(data, "reflection", ReflectionConfig))
    d = raw.pop("level_difficulty")
    return ReflectionConfig(level_difficulty=tuple(d) if isinstance(d, list) else d, **raw)


def _privacy(data: dict) -> PrivacyConfig:
    raw = dict(_section(data, "privacy", PrivacyConfig))
    if isinstance(raw["categories"], list):
        raw["categories"] = tuple(raw["categories"])
    return PrivacyConfig(**raw)


def _initiative(data: dict) -> InitiativeConfig:
    raw = _section(data, "initiative", InitiativeConfig)
    if not _is_int(raw["follow_ups_per_day"]) or raw["follow_ups_per_day"] < 0:
        raise ConfigError("initiative.follow_ups_per_day must be an integer >= 0")
    for name in ("active_start_hour", "active_end_hour"):
        if not _is_int(raw[name]) or not 0 <= raw[name] <= 23:
            raise ConfigError(f"initiative.{name} must be an hour 0-23")
    if raw["active_start_hour"] >= raw["active_end_hour"]:
        raise ConfigError("initiative.active_start_hour must be before active_end_hour")
    _number("initiative", "starter_idle_hours", raw["starter_idle_hours"], 0.0, 24 * 30)
    _number("initiative", "starter_gap_hours", raw["starter_gap_hours"], 0.0, 24 * 30)
    _number("initiative", "starter_chance", raw["starter_chance"], 0.0, 1.0)
    return InitiativeConfig(**raw)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _replies(data: dict) -> RepliesConfig:
    raw = dict(_section(data, "replies", RepliesConfig))
    for name in VARIANT_REPLIES:
        if isinstance(raw[name], list):
            raw[name] = tuple(raw[name])
    return RepliesConfig(**raw)


def load_config(path: Path = DEFAULT_CONFIG) -> Config:
    with path.open("rb") as f:
        data = tomllib.load(f)
    return Config(
        working_memory=WorkingMemoryConfig(**_section(data, "working_memory", WorkingMemoryConfig)),
        memory=MemoryConfig(**_section(data, "memory", MemoryConfig)),
        embedding=EmbeddingConfig(**_section(data, "embedding", EmbeddingConfig)),
        recall=RecallConfig(**_section(data, "recall", RecallConfig)),
        activation=_activation(data),
        generation=GenerationConfig(**_section(data, "generation", GenerationConfig)),
        session=SessionConfig(**_section(data, "session", SessionConfig)),
        mood=MoodConfig(**_section(data, "mood", MoodConfig)),
        relationship=RelationshipConfig(**_section(data, "relationship", RelationshipConfig)),
        mood_drive=MoodDriveConfig(**_section(data, "mood_drive", MoodDriveConfig)),
        privacy=_privacy(data),
        initiative=_initiative(data),
        drive=DriveConfig(**_section(data, "drive", DriveConfig)),
        reflection=_reflection(data),
        selection=SelectionConfig(**_section(data, "selection", SelectionConfig)),
        replies=_replies(data),
        encoding=_encoding(data),
    )
