from __future__ import annotations

import sys
from pathlib import Path

import pytest

from hunch import cli
from hunch.observability.turn_log import TURNS_FILE
from hunch.runtime import build_runtime, fresh_pipeline
from tests.fakes import FakeLLM, HashEmbedder


def test_build_runtime_wires_a_working_pipeline(tmp_path: Path) -> None:
    rt = build_runtime(
        db_path=tmp_path / "data" / "hunch.db",
        log_dir=tmp_path / "logs",
        model=FakeLLM(),
        embedder=HashEmbedder(1024),  # type: ignore[arg-type]
    )
    session = rt.pipeline.new_session("u_test")
    result = rt.pipeline.turn(session, "hello there")
    rt.pipeline.after_reply(session, result)
    assert result.reply
    assert len(rt.store.memories("u_test")) == 1
    assert (tmp_path / "logs" / TURNS_FILE).exists()
    rt.store.close()


def test_fresh_pipeline_starts_empty() -> None:
    pipe = fresh_pipeline(FakeLLM(), HashEmbedder(1024), seed=3)  # type: ignore[arg-type]
    assert pipe.store.memories() == []
    assert pipe.turn(pipe.new_session("u"), "hi").reply
    pipe.store.close()


def test_cli_chats_until_quit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    rt = build_runtime(
        db_path=tmp_path / "hunch.db",
        log_dir=tmp_path / "logs",
        model=FakeLLM(candidates=("Hey! How are you?",) * 3),
        embedder=HashEmbedder(1024),  # type: ignore[arg-type]
    )
    monkeypatch.setattr(cli, "build_runtime", lambda seed: rt)
    lines = iter(["hi", "", "/quit", "never read"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(lines))
    monkeypatch.setattr(sys, "argv", ["hunch.cli", "--user", "berk", "--verbose"])
    cli.main()
    out = capsys.readouterr().out
    assert out.count("hunch> Hey! How are you?") == 1
    assert "after reply" in out
