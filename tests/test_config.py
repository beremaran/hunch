from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from hunch.config import DEFAULT_CONFIG, ConfigError, load_config

REPO_TOML = DEFAULT_CONFIG.read_text(encoding="utf-8")


def test_repo_config_has_decided_working_memory_limits() -> None:
    wm = load_config().working_memory
    assert (wm.max_turns, wm.max_tokens) == (10, 2000)


def test_repo_config_embedding_runs_on_cpu() -> None:
    emb = load_config().embedding
    assert (emb.model_id, emb.device, emb.dim) == ("Qwen/Qwen3-Embedding-0.6B", "cpu", 1024)


def test_repo_config_has_approved_phase3_defaults() -> None:
    cfg = load_config()
    gen, sel = cfg.generation, cfg.selection
    assert (gen.candidates, gen.temperature, gen.top_p, gen.max_new_tokens) == (3, 0.7, 0.8, 150)
    assert (sel.quality_floor, sel.drive_weight, sel.exploration) == (6, 0.5, 0.1)
    assert (cfg.recall.similar_k, cfg.recall.min_similarity) == (20, 0.45)
    assert cfg.drive.hunch_min_intensity == 0.3
    assert cfg.session.summary_max_words == 120
    assert (cfg.mood.neutral, cfg.mood.neutral_label) == ((0.0, 0.5), "calm")
    assert cfg.replies.filter_fallback == (
        "I don't have that in mind right now. Could you tell me again?"
    )
    assert cfg.replies.gate_fallback == (
        "I'd rather not go there. Can we talk about it another way?"
    )


def test_config_is_read_only() -> None:
    cfg = load_config()
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.working_memory.max_turns = 50  # type: ignore[misc]
    with pytest.raises(TypeError):
        cfg.activation.cue_type_weights["person"] = 9.0  # type: ignore[index]


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "hunch.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_repo_config_round_trips(tmp_path: Path) -> None:
    assert load_config(_write(tmp_path, REPO_TOML)) == load_config()


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("max_turns = 10", "max_turns = 0"),
        ("max_turns = 10", "max_turns = true"),
        ("max_tokens = 2000", "max_tokens = '2000'"),
        ("max_tokens = 2000", "max_tokens = 2000\nextra = 1"),
        ("dim = 1024", "dim = -1"),
        ("max_upper_per_turn = 3", "max_upper_per_turn = 0"),
        ("involuntary_per_session = 1", "involuntary_per_session = -1"),
        ("reconsolidation_rate = 0.1", "reconsolidation_rate = 2"),
        ('db_name = "hunch.db"', ""),
        ("tau_upper = -0.5", "tau_upper = -3.0"),  # below tau_lower
        ("noise_s = 0.25", "noise_s = 'loud'"),
        ('rehearsal = "refresh"', 'rehearsal = "forever"'),
        ("refresh_strength = 0.9", "refresh_strength = 1.5"),
        ("min_cue_strength = 0.2", "min_cue_strength = -1"),
        ("emotion = 0.4", ""),  # every cue type needs a weight
        ("emotion = 0.4", "emotion = 0.4\nsmell = 1.0"),
        ("similar_k = 20", "similar_k = 0"),
        ("min_similarity = 0.45", "min_similarity = 2"),
        ("candidates = 3", "candidates = 0"),
        ("temperature = 0.7", "temperature = 0"),
        ("max_new_tokens = 150", "max_new_tokens = 1.5"),
        ("summary_max_words = 120", "summary_max_words = -5"),
        ("neutral_arousal = 0.5", "neutral_arousal = 1.5"),
        ('neutral_label = "calm"', 'neutral_label = ""'),
        ("hunch_min_intensity = 0.3", "hunch_min_intensity = 0.9"),  # above the clear bucket
        ("quality_floor = 6", "quality_floor = 11"),
        ("exploration = 0.1", "exploration = -0.1"),
        ("gate_fallback = ", "unused = "),
        ("default_affect = [0.0, 0.3]", "default_affect = [0.0]"),
        ("joy = [0.8, 0.6]", "joy = [0.8, 1.6]"),
        ("nostalgia = [0.2, 0.4]", ""),  # every emotion needs an affect
    ],
)
def test_invalid_config_rejected(tmp_path: Path, old: str, new: str) -> None:
    assert REPO_TOML.count(old) == 1, old
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, REPO_TOML.replace(old, new)))


def test_missing_section_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="working_memory"):
        load_config(_write(tmp_path, ""))
