from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from hunch.config import ConfigError, load_config


def test_repo_config_has_decided_working_memory_limits() -> None:
    wm = load_config().working_memory
    assert (wm.max_turns, wm.max_tokens) == (10, 2000)


def test_config_is_read_only() -> None:
    cfg = load_config()
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.working_memory.max_turns = 50  # type: ignore[misc]


@pytest.mark.parametrize(
    "body",
    [
        "",
        "[working_memory]\nmax_turns = 10\n",
        "[working_memory]\nmax_turns = 10\nmax_tokens = 2000\nextra = 1\n",
        "[working_memory]\nmax_turns = 0\nmax_tokens = 2000\n",
        "[working_memory]\nmax_turns = 10\nmax_tokens = '2000'\n",
        "[working_memory]\nmax_turns = true\nmax_tokens = 2000\n",
    ],
)
def test_invalid_config_rejected(tmp_path: Path, body: str) -> None:
    path = tmp_path / "hunch.toml"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(path)
