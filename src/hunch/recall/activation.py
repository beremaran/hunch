"""Activation of a memory (design.md, "Hatırlama mekanizması"); pure functions, no LLM.

    A_i = B_i + alpha * arousal_i * salience_i
          + sum_c W_c * bond_ic * max(m, S - ln fan_c|context) + mu * cos(mood, affect_i) + eps

- Base level B_i: power-law decay; t in days, floored at min_age_days so a just-created memory
  does not get infinite activation. rehearsal = "refresh" (Berk's decision): a recall makes the
  memory almost like a newly formed one again, at refresh_strength (~90 %) of a new memory's
  strength, B = ln(refresh_strength * t_last^-d); recalls do not stack up, and the memory then
  fades like any other. rehearsal = "accumulate" is the ACT-R sum over all accesses,
  ln(sum_j t_j^-d), kept for comparison.
- Encoding strength: emotionally intense, important memories start strong ("flashbulb").
- Spreading activation: only cues shared by the current message and the memory count.
  W_c = type weight of the cue x its strength in the message; bond_ic is the memory's bond to the
  cue. Fan effect: a rare cue (a song) is strong, a common one (a frequent name) weak. The fan is
  counted in context (Berk's decision): if the message shares other cues with this memory, only
  memories that also carry one of those cues count. "Anna" alone is common; "Anna" together with
  "sailing" is rare for the one memory about sailing with Anna, so there the name counts fully.
  A cue never adds less than min_cue_strength (m), so a common name still slightly favours its
  memories.
- Mood congruence: cosine between the current mood and the memory's affect, both as
  (valence, arousal - 0.5) so that arousal does not make every pair look similar.
- Noise: logistic, from a caller-supplied seeded RNG (deterministic tests).

Layer: A > tau_upper -> "upper" (content enters reasoning), tau_lower < A <= tau_upper -> "lower"
(only the lower trace acts), otherwise "none". A suppressed memory ("forget" by a user) is capped
at "lower": it never enters reasoning, but its lower trace keeps acting (design.md, "Unutma").
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal

import numpy as np

from hunch.memory.schema import Memory, cue_type

Layer = Literal["upper", "lower", "none"]
Rehearsal = Literal["refresh", "accumulate"]
SECONDS_PER_DAY = 86_400.0

# fan(cue, context) -> number of memories carrying `cue` and, if `context` is not empty, at least
# one cue of `context` as well. Always >= 1 for a cue of the memory being scored.
Fan = Callable[[str, frozenset[str]], int]


@dataclass(frozen=True, slots=True)
class ActivationParams:
    decay_d: float
    min_age_days: float
    encoding_alpha: float
    spreading_s: float
    min_cue_strength: float
    cue_type_weights: Mapping[str, float]
    mood_mu: float
    noise_s: float
    tau_upper: float
    tau_lower: float
    rehearsal: Rehearsal = "refresh"
    refresh_strength: float = 0.9

    def __post_init__(self) -> None:
        if self.rehearsal not in ("refresh", "accumulate"):
            raise ValueError(f"rehearsal must be 'refresh' or 'accumulate', got {self.rehearsal!r}")
        if not 0 < self.refresh_strength <= 1:
            raise ValueError("refresh_strength must be in (0, 1]")
        if not self.tau_lower < self.tau_upper:
            raise ValueError("tau_lower must be below tau_upper")
        if self.decay_d <= 0 or self.min_age_days <= 0 or self.noise_s < 0:
            raise ValueError("decay_d and min_age_days must be > 0, noise_s >= 0")
        if not 0 <= self.min_cue_strength <= self.spreading_s:
            raise ValueError("min_cue_strength must be in [0, spreading_s]")


@dataclass(frozen=True, slots=True)
class ActivationBreakdown:
    base: float
    encoding: float
    spreading: float
    mood: float
    noise: float

    @property
    def total(self) -> float:
        return self.base + self.encoding + self.spreading + self.mood + self.noise


def _strength(age_days: float, decay_d: float, min_age_days: float) -> float:
    return max(age_days, min_age_days) ** -decay_d


def base_level(
    created_age_days: float,
    recall_ages_days: tuple[float, ...],
    params: ActivationParams,
) -> float:
    """Base-level activation from the memory's age and the ages of its recalls."""
    d, floor = params.decay_d, params.min_age_days
    if params.rehearsal == "accumulate":
        ages = (created_age_days, *recall_ages_days)
        return math.log(sum(_strength(a, d, floor) for a in ages))
    if not recall_ages_days:
        return math.log(_strength(created_age_days, d, floor))
    last = min(recall_ages_days)
    # A recall refreshes the memory to ~90 % of a new one, unless it is still stronger anyway.
    refreshed = params.refresh_strength * _strength(last, d, floor)
    return math.log(max(refreshed, _strength(created_age_days, d, floor)))


def encoding_strength(arousal: float, salience: float, alpha: float) -> float:
    return alpha * arousal * salience


def spreading(
    message_cues: Mapping[str, float],
    memory_cues: Mapping[str, float],
    fan: Fan,
    spreading_s: float,
    cue_type_weights: Mapping[str, float],
    min_cue_strength: float,
) -> float:
    shared = frozenset(message_cues) & frozenset(memory_cues)
    total = 0.0
    for cue in shared:
        context = shared - {cue}  # the other cues this message and this memory have in common
        strength = max(min_cue_strength, spreading_s - math.log(max(fan(cue, context), 1)))
        weight = cue_type_weights[cue_type(cue)] * message_cues[cue]
        total += weight * memory_cues[cue] * strength
    return total


def mood_congruence(mood: tuple[float, float], affect: tuple[float, float], mu: float) -> float:
    a = np.array([mood[0], mood[1] - 0.5])
    b = np.array([affect[0], affect[1] - 0.5])
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return mu * float(a @ b / (na * nb))


def logistic_noise(rng: np.random.Generator, s: float) -> float:
    if s == 0:
        return 0.0
    u = rng.uniform(1e-12, 1 - 1e-12)
    return s * math.log(u / (1 - u))


def activation(
    memory: Memory,
    now: float,
    message_cues: Mapping[str, float],
    fan: Fan,
    mood: tuple[float, float],
    params: ActivationParams,
    rng: np.random.Generator,
) -> ActivationBreakdown:
    """All components of A_i for one memory at time `now` (unix seconds)."""
    created = (now - memory.created_at) / SECONDS_PER_DAY
    recalls = tuple((now - t) / SECONDS_PER_DAY for t in memory.access_times)
    return ActivationBreakdown(
        base=base_level(created, recalls, params),
        encoding=encoding_strength(memory.affect[1], memory.salience, params.encoding_alpha),
        spreading=spreading(
            message_cues,
            memory.cues,
            fan,
            params.spreading_s,
            params.cue_type_weights,
            params.min_cue_strength,
        ),
        mood=mood_congruence(mood, memory.affect, params.mood_mu),
        noise=logistic_noise(rng, params.noise_s),
    )


def layer(total: float, params: ActivationParams, suppressed: bool = False) -> Layer:
    if total > params.tau_upper:
        return "lower" if suppressed else "upper"
    if total > params.tau_lower:
        return "lower"
    return "none"


def fan_from_cue_sets(cue_sets: list[frozenset[str]]) -> Fan:
    """Context-aware fan over an in-memory collection (simulation, tests)."""

    def fan(cue: str, context: frozenset[str]) -> int:
        return sum(1 for cues in cue_sets if cue in cues and (not context or cues & context))

    return fan
