"""The model a long-lived process already holds, lent to in-process golden tests (Phase 7: the
nightly step 8 runs inside the bot, where a second copy of the model does not fit in VRAM)."""

from __future__ import annotations

_shared: tuple[object, object] | None = None


def lend(model: object, embedder: object) -> None:
    global _shared
    _shared = (model, embedder)


def borrowed() -> tuple[object, object] | None:
    return _shared
