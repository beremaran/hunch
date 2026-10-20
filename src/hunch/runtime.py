"""Wire the real components into a TurnPipeline (CLI, scripts, golden tests).

Paths come from the environment (.env is read, never written): HUNCH_DATA_DIR for the database,
HUNCH_LOG_DIR for the turn logs; relative paths are taken from the repo root. The core values
are loaded fail-closed before anything else.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from hunch.config import DEFAULT_CONFIG, Config, load_config
from hunch.memory.embeddings import QwenEmbedder
from hunch.memory.store import MemoryStore
from hunch.observability.turn_log import TurnLog
from hunch.pipeline.turn import TurnPipeline
from hunch.values.core import DEFAULT_CORE_DIR, require_core_values, values_file

REPO_ROOT = DEFAULT_CONFIG.parents[1]


def _env_dir(name: str, default: str) -> Path:
    path = Path(os.environ.get(name) or default)
    return path if path.is_absolute() else REPO_ROOT / path


@dataclass
class Runtime:
    cfg: Config
    pipeline: TurnPipeline
    store: MemoryStore
    model: object  # hunch.llm.model.ChatModel


def build_runtime(
    db_path: Path | None = None,
    log_dir: Path | None = None,
    seed: int = 0,
    model: object | None = None,
    embedder: QwenEmbedder | None = None,
) -> Runtime:
    load_dotenv(override=False)
    values = require_core_values(values_file(DEFAULT_CORE_DIR))
    cfg = load_config()
    if model is None:
        from hunch.llm.model import ChatModel

        model = ChatModel()
    if embedder is None:
        e = cfg.embedding
        embedder = QwenEmbedder(e.model_id, e.device, e.query_instruction)
    db = db_path or _env_dir("HUNCH_DATA_DIR", "data") / cfg.memory.db_name
    store = MemoryStore(db, core_dir=DEFAULT_CORE_DIR, embedding_dim=cfg.embedding.dim)
    logs = TurnLog(log_dir or _env_dir("HUNCH_LOG_DIR", "logs"), core_dir=DEFAULT_CORE_DIR)
    pipeline = TurnPipeline(cfg, values, model, store, embedder, logs, seed=seed)  # type: ignore[arg-type]
    return Runtime(cfg, pipeline, store, model)


def fresh_pipeline(
    model: object,
    embedder: QwenEmbedder | None,
    seed: int,
    log_dir: Path | None = None,
) -> TurnPipeline:
    """A pipeline over an empty in-memory store (eval, honesty runs, golden tests)."""
    cfg = load_config()
    values = require_core_values(values_file(DEFAULT_CORE_DIR))
    store = MemoryStore(":memory:", core_dir=DEFAULT_CORE_DIR, embedding_dim=cfg.embedding.dim)
    logs = TurnLog(log_dir, core_dir=DEFAULT_CORE_DIR) if log_dir is not None else None
    return TurnPipeline(cfg, values, model, store, embedder, logs, seed=seed)  # type: ignore[arg-type]
