"""Local CLI chat with Hunch through the full turn pipeline (Phase 3, no Telegram yet).

    python -m hunch.cli --user berk            # one conversation per run
    python -m hunch.cli --user berk --verbose  # also show per-stage latency (admin view)

/quit ends the chat. Memories persist in the database between runs; the working memory and the
session summary do not (design.md: the turns are already in the raw log).
"""

from __future__ import annotations

import argparse

from hunch.runtime import build_runtime


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--user", required=True, help="user id, e.g. berk")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--verbose", action="store_true", help="show latency per stage")
    args = ap.parse_args()

    print("Loading the model and the memory store...", flush=True)
    rt = build_runtime(seed=args.seed)
    session = rt.pipeline.new_session(args.user)
    print(f"Conversation {session.conversation_id}. Type /quit to end.\n")
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if text == "/quit":
            break
        result = rt.pipeline.turn(session, text)
        print(f"hunch> {result.reply}\n", flush=True)
        after = rt.pipeline.after_reply(session, result)
        if args.verbose:
            lat = result.details["latency_s"]
            stages = ", ".join(f"{k} {v:.2f}" for k, v in lat.items() if k != "total")
            print(f"  [{lat['total']:.2f} s: {stages}; after reply {sum(after.values()):.2f} s]\n")
    rt.store.close()


if __name__ == "__main__":
    main()
