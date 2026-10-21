"""Admin commands over the memory store (Phase 5; Telegram /forget follows in Phase 6).

    python -m hunch.admin find "salary" [--user berk]   # look up memory ids
    python -m hunch.admin forget <memory id> [--reason "..."]
    python -m hunch.admin archive                       # what admin forgets removed

`forget` is the admin "forget" (design.md "Unutma"): the memory, its derived realisations,
beliefs and hunch source refs leave every AI-visible store; the raw turn stays, hidden from AI
views, and a copy goes to the append-only admin archive. No model is loaded.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime

from hunch.config import load_config
from hunch.memory.forget import admin_forget
from hunch.memory.store import MemoryStore
from hunch.runtime import env_dir, load_env
from hunch.values.core import DEFAULT_CORE_DIR


def _store() -> MemoryStore:
    load_env()
    cfg = load_config()
    db = env_dir("HUNCH_DATA_DIR", "data") / cfg.memory.db_name
    return MemoryStore(db, core_dir=DEFAULT_CORE_DIR, embedding_dim=cfg.embedding.dim)


def _when(t: float) -> str:
    return datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("find", help="memories whose text contains a phrase")
    f.add_argument("text")
    f.add_argument("--user")
    g = sub.add_parser("forget", help="admin forget of one memory")
    g.add_argument("memory_id")
    g.add_argument("--reason", default="admin forget")
    sub.add_parser("archive", help="show the admin archive")
    args = ap.parse_args(argv)

    store = _store()
    try:
        if args.cmd == "find":
            needle = args.text.casefold()
            for m in store.memories(args.user):
                if needle in m.summary.casefold():
                    flags = ",".join(
                        x for x, on in (("suppressed", m.suppressed), (m.kind, True)) if on
                    )
                    print(f"{m.id}  {m.owner_user}  {m.privacy}  {flags}  {_when(m.created_at)}")
                    print(f"    {m.summary[:120]}")
        elif args.cmd == "forget":
            r = admin_forget(store, args.memory_id, args.reason, time.time())
            print(json.dumps(r.__dict__, indent=2))
        else:
            for a in store.archive():
                print(f"{_when(a['t'])}  {a['kind']}  {a['id']}  {a['owner_user']}  {a['reason']}")
    finally:
        store.close()


if __name__ == "__main__":
    main()
