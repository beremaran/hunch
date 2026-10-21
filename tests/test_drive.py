from __future__ import annotations

import numpy as np
import pytest

from hunch.config import load_config
from hunch.drive.drive import (
    DriveVector,
    LowerTrace,
    candidate_features,
    compute_drive,
    drive_score,
    hunch_flag,
    trace_weight,
)
from hunch.drive.modulation import Scored, select

PARAMS = load_config().activation  # tau_lower -1.5, tau_upper -0.5


def test_no_traces_give_a_neutral_drive_and_no_hunch() -> None:
    assert compute_drive([], PARAMS).is_neutral
    assert hunch_flag([], PARAMS, 0.3, "h-1") is None


def test_trace_weight_rises_from_tau_lower_to_tau_upper() -> None:
    assert trace_weight(LowerTrace(-1.5, 0, 0.5, 0.5), PARAMS) == 0.0
    assert trace_weight(LowerTrace(-1.0, 0, 0.5, 0.5), PARAMS) == pytest.approx(0.5)
    assert trace_weight(LowerTrace(-0.5, 0, 0.5, 0.5), PARAMS) == 1.0
    assert trace_weight(LowerTrace(2.0, 0, 0.5, 0.5, capped=True), PARAMS) == 1.0


def test_negative_traces_cool_warmth_and_raise_caution() -> None:
    drive = compute_drive([LowerTrace(-0.6, -0.8, 0.9, 0.9)], PARAMS)
    assert drive.warmth < 0.5 < drive.caution
    assert drive.energy > 0.5  # high arousal
    assert drive.curiosity == 0.5  # no input in Phase 3


def test_positive_traces_warm_up_and_lower_caution() -> None:
    drive = compute_drive([LowerTrace(-0.6, 0.8, 0.2, 0.9)], PARAMS)
    assert drive.warmth > 0.5 > drive.caution
    assert drive.energy < 0.5  # low arousal


def test_hunch_flag_only_from_the_minimum_intensity() -> None:
    weak = [LowerTrace(-1.4, -0.5, 0.3, 0.3)]
    strong = [LowerTrace(-0.6, -0.5, 0.9, 0.9)]
    assert hunch_flag(weak, PARAMS, 0.3, "h-1") is None
    flag = hunch_flag(strong, PARAMS, 0.3, "h-1")
    assert flag is not None and flag.valence < 0 and flag.intensity >= 0.3


def test_candidate_features() -> None:
    warm = candidate_features("I'm so sorry, that must be really hard. I'm here for you.")
    curious = candidate_features("What happened? How do you feel about it?")
    cautious = candidate_features("Maybe it depends, I'm not sure. Perhaps wait a bit.")
    energetic = candidate_features("Yes! Amazing!")
    assert warm.warmth == 1.0 and curious.warmth == 0.0
    assert curious.curiosity == 1.0 and warm.curiosity == 0.0
    assert cautious.caution == 1.0
    assert energetic.energy > warm.energy


def test_neutral_drive_has_no_preference() -> None:
    f1, f2 = candidate_features("Sorry!"), candidate_features("Maybe?")
    assert drive_score(DriveVector(), f1) == drive_score(DriveVector(), f2) == 0.5


def test_drive_score_prefers_candidates_leaning_the_drives_way() -> None:
    cold = DriveVector(warmth=0.3, caution=0.7)
    warm_reply = candidate_features("I'm so sorry, that must be hard.")
    careful_reply = candidate_features("Maybe wait, perhaps it depends.")
    assert drive_score(cold, careful_reply) > 0.5 > drive_score(cold, warm_reply)


def _rng(seed: int = 0) -> np.random.Generator:
    return np.random.default_rng(seed)


def test_selection_never_picks_below_the_quality_floor() -> None:
    cands = [Scored("a", 5, 1.0), Scored("b", 7, 1.0), Scored("c", 9, 0.0)]
    sel = select(cands, 6, 10.0, 0.0, False, _rng())
    assert "a" not in sel.order
    assert sel.order[0] == "b" and sel.chosen_by == "drive"


def test_selection_by_quality_when_drive_is_neutral() -> None:
    cands = [Scored("a", 7, 0.5), Scored("b", 9, 0.5)]
    sel = select(cands, 6, 0.5, 1.0, True, _rng())  # exploration has no effect without a drive
    assert sel.order == ("b", "a") and sel.chosen_by == "quality" and not sel.explored


def test_exploration_picks_the_least_fitting_candidate_above_the_floor() -> None:
    cands = [Scored("a", 8, 0.9), Scored("b", 8, 0.2), Scored("c", 3, 0.0)]
    sel = select(cands, 6, 0.5, 1.0, False, _rng())
    assert sel.order[0] == "b" and sel.chosen_by == "exploration" and "c" not in sel.order


def test_exploration_rate_matches_config_over_many_turns() -> None:
    rng = _rng(7)
    cands = [Scored("a", 8, 0.9), Scored("b", 8, 0.2)]
    explored = sum(select(cands, 6, 0.5, 0.1, False, rng).explored for _ in range(5000))
    assert 0.08 < explored / 5000 < 0.12


def test_below_floor_falls_back_to_best_quality_and_says_so() -> None:
    sel = select([Scored("a", 4, 1.0), Scored("b", 5, 0.0)], 6, 0.5, 0.0, False, _rng())
    assert sel.order == ("b", "a") and sel.chosen_by == "below_floor"


def test_no_rated_candidate_gives_no_choice() -> None:
    sel = select([Scored("a", None, 1.0)], 6, 0.5, 0.0, False, _rng())
    assert sel.order == () and sel.chosen_by is None


def test_intensity_is_the_mean_so_many_weak_traces_do_not_add_up() -> None:
    weak = LowerTrace(-0.6, -0.5, 0.6, 0.6)  # weight 0.9, arousal x salience 0.36
    one = hunch_flag([weak], PARAMS, 0.3, "h-1")
    many = hunch_flag([weak] * 10, PARAMS, 0.3, "h-1")
    assert one is not None and many is not None
    assert many.intensity == pytest.approx(one.intensity)
    faint = LowerTrace(-1.4, -0.5, 0.5, 0.5)
    assert hunch_flag([faint] * 20, PARAMS, 0.3, "h-1") is None


def test_gated_traces_count_by_their_relevance() -> None:
    from hunch.pipeline.turn import gated_weight

    assert gated_weight(0.9, 0.45) == 1.0
    assert gated_weight(0.225, 0.45) == pytest.approx(0.5)
    assert gated_weight(-0.2, 0.45) == 0.0
    assert gated_weight(None, 0.45) == 0.0
    gated = LowerTrace(2.0, -0.9, 0.9, 0.9, weight=0.1)
    assert trace_weight(gated, PARAMS) == pytest.approx(0.1)


def test_drive_score_counts_the_drive_size_below_full_scale() -> None:
    # Berk (Phase 5): a drive smaller than full_scale steers proportionally less.
    from hunch.drive.drive import NEUTRAL

    careful = DriveVector(warmth=0.0, caution=1.0, curiosity=0.5, energy=0.5)
    big = DriveVector(warmth=0.45, caution=0.55)  # total deviation 0.1
    tiny = DriveVector(warmth=0.49, caution=0.51)  # total deviation 0.02
    lean_big = drive_score(big, careful, 0.1) - NEUTRAL
    lean_tiny = drive_score(tiny, careful, 0.1) - NEUTRAL
    assert lean_big > 0 and abs(lean_tiny - lean_big * 0.2) < 1e-9
    # At or above full_scale only the direction counts, as in Phases 3-4.
    assert drive_score(big, careful, 0.1) == drive_score(big, careful)


def test_compute_drive_adds_mood_terms_before_clipping() -> None:
    params = load_config().activation
    d = compute_drive([], params, {"warmth": 0.2, "curiosity": -0.1, "caution": 0.9})
    assert (d.warmth, d.curiosity, d.caution, d.energy) == (0.7, 0.4, 1.0, 0.5)
