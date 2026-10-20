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
    ],
)
def test_invalid_config_rejected(tmp_path: Path, old: str, new: str) -> None:
    assert REPO_TOML.count(old) == 1, old
    with pytest.raises(ConfigError):
        load_config(_write(tmp_path, REPO_TOML.replace(old, new)))


def test_missing_section_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="working_memory"):
        load_config(_write(tmp_path, ""))
