"""Candidate selection (design.md, "Dürtü vektörü ve modülasyon", MVP stage 1).

Only candidates at or above the quality floor can be chosen by modulation (invariant 5). Among
them, score = quality / 10 + drive_weight x drive_score; with a small probability (exploration)
the least drive-fitting candidate is picked instead, so a wrong bias can be corrected by new
evidence. If no candidate reaches the floor, modulation does not choose: the best-quality
candidate is used. The value gate runs after this, on the returned order.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

ChosenBy = Literal["quality", "drive", "exploration", "only_candidate", "below_floor"]


@dataclass(frozen=True, slots=True)
class Scored:
    id: str
    quality: float | None  # judge score 1-10; None if the judge gave none
    drive_score: float


@dataclass(frozen=True, slots=True)
class Selection:
    order: tuple[str, ...]  # chosen first, then the fallbacks the value gate may try
    chosen_by: ChosenBy | None  # None: no candidate at all
    explored: bool


def select(
    candidates: Sequence[Scored],
    quality_floor: float,
    drive_weight: float,
    exploration: float,
    drive_is_neutral: bool,
    rng: np.random.Generator,
) -> Selection:
    explore_draw = rng.random()  # always drawn once per turn, so runs stay comparable
    above = [c for c in candidates if c.quality is not None and c.quality >= quality_floor]
    if not above:
        rated = sorted(
            (c for c in candidates if c.quality is not None), key=lambda c: -(c.quality or 0)
        )
        order = tuple(c.id for c in rated)
        return Selection(order, "below_floor" if order else None, False)

    def score(c: Scored) -> float:
        return (c.quality or 0) / 10 + drive_weight * c.drive_score

    by_score = sorted(above, key=score, reverse=True)  # stable: ties keep candidate order
    best_quality = max(above, key=lambda c: c.quality or 0)
    if len(above) == 1:
        return Selection((above[0].id,), "only_candidate", False)
    if not drive_is_neutral and explore_draw < exploration:
        least = min(above, key=lambda c: c.drive_score)
        rest = [c.id for c in by_score if c.id != least.id]
        return Selection((least.id, *rest), "exploration", True)
    chosen_by: ChosenBy = "drive" if by_score[0].id != best_quality.id else "quality"
    return Selection(tuple(c.id for c in by_score), chosen_by, False)
