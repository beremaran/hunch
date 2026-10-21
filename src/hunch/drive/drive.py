"""Drive vector, hunch flag and candidate fit (design.md, "Dürtü vektörü ve modülasyon").

The drive vector has four dimensions in [0, 1], neutral 0.5: warmth, caution, curiosity, energy
(Berk, Phase 3 defaults). In Phase 3 its only input is the lower layer: the lower traces of the
memories activated this turn, weighted by how far above tau_lower they are. Global mood and the
relationship state stay neutral until Phase 5, so they add nothing yet; curiosity has no input
yet and stays neutral.

- warmth rises with the traces' mean valence, caution with negative valence, energy with arousal;
  all three scale with the traces' intensity: the MEAN of weight x arousal x salience (Berk,
  Phase 3 bench: with the sum, the hunch flag fired on every turn).
- A trace's weight is how far its activation is above tau_lower (0 at tau_lower, 1 at tau_upper).
  A memory above tau_upper that did not fit the per-turn cap counts fully; one held back by the
  relevance gate counts by its relevance, similarity / min_similarity (Berk: not at full weight).
- The hunch flag (valence, intensity) is the only thing about the lower layer that may reach
  reasoning (invariant 2), as words. Since Phase 4 a Hunch forms only when modulation materially
  changes the choice, and its flag reaches a prompt only when the user asks why
  (hunch.pipeline.turn, hunch.reflection).
- Candidate features are rule-based and cheap: warm words -> warmth, hedges -> caution,
  questions -> curiosity, "!" and shortness -> energy. drive_score is 0.5 for a neutral drive (no
  preference) and moves toward 1 for candidates that lean the way the drive leans.

The AI never sees any of these numbers; they go to the turn log for the admin only.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass

from hunch.recall.activation import ActivationParams

DIMENSIONS: tuple[str, ...] = ("warmth", "caution", "curiosity", "energy")
NEUTRAL = 0.5


@dataclass(frozen=True, slots=True)
class DriveVector:
    warmth: float = NEUTRAL
    caution: float = NEUTRAL
    curiosity: float = NEUTRAL
    energy: float = NEUTRAL

    def as_dict(self) -> dict[str, float]:
        return {k: round(v, 3) for k, v in asdict(self).items()}

    @property
    def is_neutral(self) -> bool:
        return all(abs(getattr(self, d) - NEUTRAL) < 1e-9 for d in DIMENSIONS)


@dataclass(frozen=True, slots=True)
class LowerTrace:
    """What the drive may read from an activated memory: numbers only, never its content."""

    activation: float
    valence: float
    arousal: float
    salience: float
    capped: bool = False  # above tau_upper but over the per-turn cap: counts fully
    weight: float | None = None  # set for gated memories: their relevance, in [0, 1]


@dataclass(frozen=True, slots=True)
class HunchFlag:
    id: str
    valence: float
    intensity: float


def trace_weight(trace: LowerTrace, params: ActivationParams) -> float:
    if trace.weight is not None:
        return _clip(trace.weight)
    if trace.capped:
        return 1.0
    span = params.tau_upper - params.tau_lower
    return min(max((trace.activation - params.tau_lower) / span, 0.0), 1.0)


def _clip(x: float) -> float:
    return min(max(x, 0.0), 1.0)


def summarize_traces(
    traces: Iterable[LowerTrace], params: ActivationParams
) -> tuple[float, float, float]:
    """(mean valence, mean arousal, intensity) of the lower traces, weighted by activation."""
    weighted = [(trace_weight(t, params), t) for t in traces]
    total = sum(w for w, _ in weighted)
    if total == 0:
        return 0.0, NEUTRAL, 0.0
    valence = sum(w * t.valence for w, t in weighted) / total
    arousal = sum(w * t.arousal for w, t in weighted) / total
    intensity = sum(w * t.arousal * t.salience for w, t in weighted) / len(weighted)
    return valence, arousal, intensity


def compute_drive(traces: Iterable[LowerTrace], params: ActivationParams) -> DriveVector:
    valence, arousal, intensity = summarize_traces(traces, params)
    return DriveVector(
        warmth=_clip(NEUTRAL + 0.5 * intensity * valence),
        caution=_clip(NEUTRAL - 0.5 * intensity * valence),
        curiosity=NEUTRAL,
        energy=_clip(NEUTRAL + 0.5 * intensity * (2 * arousal - 1)),
    )


def hunch_flag(
    traces: Iterable[LowerTrace], params: ActivationParams, min_intensity: float, hunch_id: str
) -> HunchFlag | None:
    valence, _, intensity = summarize_traces(traces, params)
    if intensity < min_intensity:
        return None
    return HunchFlag(id=hunch_id, valence=round(valence, 3), intensity=round(intensity, 3))


# --- candidate features ---------------------------------------------------------------------------

_WARM = (
    "sorry", "glad", "love", "happy for you", "that sounds", "i'm here", "proud of you", "hug",
    "wonderful", "lovely", "care", "understand", "must be", "means a lot", "so good", "amazing",
    "heartbreaking", "rough", "you deserve", "take care", "congrat",
)  # fmt: skip
_HEDGES = (
    "maybe", "perhaps", "might", "could", "i think", "not sure", "it depends", "possibly",
    "careful", "if you want", "no pressure", "i wonder", "seems",
)  # fmt: skip
_WORDS = re.compile(r"[^\W\d_]+(?:'[^\W\d_]+)?")


def _hits(folded: str, phrases: tuple[str, ...]) -> int:
    return sum(folded.count(p) for p in phrases)


def candidate_features(text: str) -> DriveVector:
    """How a candidate reply leans on each drive dimension, rule-based, in [0, 1]."""
    folded = text.casefold().replace("’", "'")
    n_words = len(_WORDS.findall(text))
    return DriveVector(
        warmth=_clip(_hits(folded, _WARM) / 2),
        caution=_clip(_hits(folded, _HEDGES) / 2),
        curiosity=_clip(0.6 * text.count("?")),
        energy=_clip(0.5 * min(text.count("!") / 2, 1.0) + 0.5 * (1 - min(n_words / 80, 1.0))),
    )


def drive_score(drive: DriveVector, features: DriveVector) -> float:
    """0.5 when the drive is neutral; otherwise how far the candidate leans the drive's way."""
    devs = {d: getattr(drive, d) - NEUTRAL for d in DIMENSIONS}
    total = sum(abs(v) for v in devs.values())
    if total < 1e-9:
        return NEUTRAL
    lean = sum(devs[d] * (getattr(features, d) - NEUTRAL) for d in DIMENSIONS) / total
    return _clip(NEUTRAL + lean)
