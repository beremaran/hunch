from __future__ import annotations

import math

import numpy as np
import pytest

from hunch.config import load_config
from hunch.memory.schema import Memory
from hunch.recall.activation import (
    SECONDS_PER_DAY,
    ActivationParams,
    activation,
    base_level,
    encoding_strength,
    fan_from_cue_sets,
    layer,
    logistic_noise,
    mood_congruence,
    spreading,
)

WEIGHTS = {t: 1.0 for t in ("person", "place", "song", "film", "date", "emotion", "phrase")}
S, FLOOR = 3.0, 0.2


def params(**kw: object) -> ActivationParams:
    base = {
        "decay_d": 0.5,
        "min_age_days": 1 / 24,
        "encoding_alpha": 3.0,
        "spreading_s": S,
        "min_cue_strength": FLOOR,
        "cue_type_weights": WEIGHTS,
        "mood_mu": 0.5,
        "noise_s": 0.0,
        "tau_upper": -0.5,
        "tau_lower": -1.5,
        "rehearsal": "refresh",
        "refresh_strength": 0.9,
    }
    return ActivationParams(**{**base, **kw})


def global_fan(counts: dict[str, int]):
    return lambda cue, context: counts[cue]


# --- base level ----------------------------------------------------------------------------------


def test_new_memory_power_law() -> None:
    p = params()
    assert base_level(1.0, (), p) == pytest.approx(0.0)
    assert base_level(4.0, (), p) == pytest.approx(math.log(4.0**-0.5))
    assert base_level(30.0, (), p) < base_level(3.0, (), p)


def test_very_recent_ages_are_floored() -> None:
    assert base_level(0.0, (), params()) == pytest.approx(math.log((1 / 24) ** -0.5))


def test_recall_refreshes_to_90_percent_of_a_new_memory() -> None:
    """Berk: a recall makes the memory ~90 % of a new one, for that moment; then it fades."""
    p = params()
    for since_recall in (0.0, 1.0, 10.0, 60.0):
        recalled = base_level(100.0 + since_recall, (since_recall,), p)
        new = base_level(since_recall, (), p)
        assert recalled == pytest.approx(new + math.log(0.9))


def test_recalls_do_not_stack() -> None:
    p = params()
    once = base_level(100.0, (1.0,), p)
    many = base_level(100.0, tuple(float(d) for d in range(1, 50)), p)
    assert once == pytest.approx(many)


def test_recall_never_lowers_a_still_fresh_memory() -> None:
    """A recall right after creation must not drop it to 90 %."""
    p = params()
    assert base_level(0.5, (2.0,), p) == pytest.approx(base_level(0.5, (), p))


def test_accumulate_mode_stacks_recalls() -> None:
    recalls = tuple(float(d) for d in range(1, 50))
    refresh = base_level(100.0, recalls, params())
    stacked = base_level(100.0, recalls, params(rehearsal="accumulate"))
    assert stacked > refresh + 1.0


@pytest.mark.parametrize("kw", [{"rehearsal": "forever"}, {"refresh_strength": 0.0},
                                {"refresh_strength": 1.5}])  # fmt: skip
def test_rehearsal_params_validated(kw: dict) -> None:
    with pytest.raises(ValueError):
        params(**kw)


# --- encoding, spreading, mood -------------------------------------------------------------------


def test_encoding_strength_flashbulb() -> None:
    assert encoding_strength(1.0, 1.0, 3.0) == 3.0
    assert encoding_strength(0.9, 0.9, 3.0) > encoding_strength(0.2, 0.9, 3.0)


def test_rare_cue_beats_common_cue() -> None:
    fan = global_fan({"song:hallelujah": 1, "person:anna": 10})
    cues = {"song:hallelujah": 0.8, "person:anna": 0.8}
    song = spreading({"song:hallelujah": 1.0}, cues, fan, S, WEIGHTS, FLOOR)
    name = spreading({"person:anna": 1.0}, cues, fan, S, WEIGHTS, FLOOR)
    assert song == pytest.approx(0.8 * S)
    assert name == pytest.approx(0.8 * (S - math.log(10)))
    assert song > name > 0


def test_very_common_cue_still_gives_the_minimum() -> None:
    """Berk: a common name still favours its memories a little."""
    fan = global_fan({"person:anna": 500})
    got = spreading({"person:anna": 1.0}, {"person:anna": 1.0}, fan, S, WEIGHTS, FLOOR)
    assert got == pytest.approx(FLOOR)


def test_only_shared_cues_spread() -> None:
    fan = global_fan({"song:x": 1, "place:berlin": 1})
    assert spreading({"song:x": 1.0}, {"place:berlin": 1.0}, fan, S, WEIGHTS, FLOOR) == 0.0


def test_cue_type_weights_and_message_strength_scale_spreading() -> None:
    fan = global_fan({"emotion:sad": 1})
    weights = {**WEIGHTS, "emotion": 0.4}
    full = spreading({"emotion:sad": 1.0}, {"emotion:sad": 1.0}, fan, S, weights, FLOOR)
    half = spreading({"emotion:sad": 0.5}, {"emotion:sad": 1.0}, fan, S, weights, FLOOR)
    assert full == pytest.approx(0.4 * S)
    assert half == pytest.approx(full / 2)


def test_common_name_counts_fully_in_context() -> None:
    """Berk's sailing example: "Anna" alone does not bring back sailing with Anna; a question
    about the Anna you went sailing with does, and there the name itself counts fully."""
    sailing = frozenset({"person:anna", "phrase:sailing"})
    others = [frozenset({"person:anna", f"phrase:thing{i}"}) for i in range(30)]
    fan = fan_from_cue_sets([sailing, *others])
    mem = {"person:anna": 1.0, "phrase:sailing": 1.0}
    other = {"person:anna": 1.0, "phrase:thing0": 1.0}

    anna_alone = spreading({"person:anna": 1.0}, mem, fan, S, WEIGHTS, FLOOR)
    other_alone = spreading({"person:anna": 1.0}, other, fan, S, WEIGHTS, FLOOR)
    assert anna_alone == pytest.approx(other_alone) == pytest.approx(FLOOR)

    msg = {"person:anna": 1.0, "phrase:sailing": 1.0}
    in_context = spreading(msg, mem, fan, S, WEIGHTS, FLOOR)
    sailing_only = spreading({"phrase:sailing": 1.0}, mem, fan, S, WEIGHTS, FLOOR)
    assert in_context - sailing_only == pytest.approx(S)  # the name now counts fully
    # Other Anna memories gain nothing from the sailing context.
    assert spreading(msg, other, fan, S, WEIGHTS, FLOOR) == pytest.approx(FLOOR)


def test_context_fan_counts_memories_sharing_cue_and_context() -> None:
    fan = fan_from_cue_sets(
        [frozenset({"person:anna", "phrase:sailing"}), frozenset({"person:anna"}),
         frozenset({"person:anna", "phrase:sailing", "place:lake"})]
    )  # fmt: skip
    assert fan("person:anna", frozenset()) == 3
    assert fan("person:anna", frozenset({"phrase:sailing"})) == 2
    assert fan("person:anna", frozenset({"place:lake"})) == 1


def test_mood_congruence() -> None:
    assert mood_congruence((0.8, 0.8), (0.8, 0.8), 0.5) == pytest.approx(0.5)
    assert mood_congruence((0.8, 0.8), (-0.8, 0.2), 0.5) == pytest.approx(-0.5)
    assert mood_congruence((0.0, 0.5), (0.8, 0.8), 0.5) == 0.0  # neutral mood


def test_arousal_alone_does_not_make_moods_congruent() -> None:
    assert mood_congruence((0.9, 0.3), (-0.9, 0.3), 0.5) < 0


# --- noise ---------------------------------------------------------------------------------------


def test_noise_is_deterministic_with_a_seed() -> None:
    a = [logistic_noise(np.random.default_rng(7), 0.25) for _ in range(3)]
    b = [logistic_noise(np.random.default_rng(7), 0.25) for _ in range(3)]
    assert a == b


def test_noise_has_logistic_scale() -> None:
    rng = np.random.default_rng(1)
    xs = np.array([logistic_noise(rng, 0.25) for _ in range(20_000)])
    assert abs(xs.mean()) < 0.02
    assert xs.var() == pytest.approx(0.25**2 * math.pi**2 / 3, rel=0.05)


def test_zero_noise_scale_is_exactly_zero() -> None:
    assert logistic_noise(np.random.default_rng(0), 0.0) == 0.0


# --- full activation and layers ------------------------------------------------------------------


def _mem(**kw: object) -> Memory:
    base = {
        "id": "m1",
        "owner_user": "u_anna",
        "privacy": "general",
        "episode_ref": "e1",
        "summary": "s",
        "cues": {"song:hallelujah": 1.0},
        "affect": (0.6, 0.8),
        "salience": 0.9,
        "created_at": 0.0,
    }
    return Memory(**{**base, **kw})


def test_activation_sums_its_components() -> None:
    now = 4 * SECONDS_PER_DAY
    b = activation(
        _mem(), now, {"song:hallelujah": 1.0}, global_fan({"song:hallelujah": 1}), (0.6, 0.8),
        params(), np.random.default_rng(0),
    )  # fmt: skip
    assert b.base == pytest.approx(math.log(4.0**-0.5))
    assert b.encoding == pytest.approx(3.0 * 0.8 * 0.9)
    assert b.spreading == pytest.approx(S)
    assert b.mood == pytest.approx(0.5)
    assert b.noise == 0.0
    assert b.total == pytest.approx(b.base + b.encoding + b.spreading + b.mood)


def test_activation_uses_recall_times() -> None:
    now = 30 * SECONDS_PER_DAY
    rng = np.random.default_rng(0)
    fan = global_fan({})
    plain = activation(_mem(), now, {}, fan, (0, 0.5), params(), rng)
    recalled = activation(
        _mem(access_times=(29 * SECONDS_PER_DAY,)), now, {}, fan, (0, 0.5), params(), rng
    )
    assert recalled.base > plain.base


@pytest.mark.parametrize(
    ("total", "suppressed", "expected"),
    [
        (0.0, False, "upper"),
        (-0.5, False, "lower"),  # tau_upper itself is not above
        (-1.0, False, "lower"),
        (-1.5, False, "none"),
        (-3.0, False, "none"),
        (0.0, True, "lower"),  # user "forget": never enters reasoning, lower trace still acts
        (-3.0, True, "none"),
    ],
)
def test_layers(total: float, suppressed: bool, expected: str) -> None:
    assert layer(total, params(), suppressed=suppressed) == expected


@pytest.mark.parametrize(
    "kw", [{"tau_upper": -2.0, "tau_lower": -1.0}, {"min_cue_strength": -0.1},
           {"min_cue_strength": 5.0}],
)  # fmt: skip
def test_params_validated(kw: dict) -> None:
    with pytest.raises(ValueError):
        params(**kw)


def test_repo_config_loads_activation_params() -> None:
    p = load_config().activation
    assert p.decay_d == 0.5  # design.md
    assert p.rehearsal == "refresh" and p.refresh_strength == 0.9  # Berk
    assert p.min_cue_strength > 0  # Berk: a common name still gives a small bonus
    assert p.tau_lower < p.tau_upper
    assert p.cue_type_weights["person"] == p.cue_type_weights["song"] == 1.0
