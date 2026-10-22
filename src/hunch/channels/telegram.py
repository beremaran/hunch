"""Telegram channel (Phase 6): long polling with python-telegram-bot, scheduled follow-ups and
hourly conversation starters through APScheduler. Run with `python -m hunch.channels.telegram`.

Secrets come from .env, read only: TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_USER_ID (the admin's
chat id, as documented in .env.example).
Each Telegram chat becomes one user by its /start <name> (see HunchChannel). Requires the model
on the GPU: one job at a time, so every model call goes through HunchChannel's lock.
"""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import Future

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from hunch.channels.hunch_channel import HunchChannel
from hunch.channels.store import ChannelStore
from hunch.loops.scheduler import FollowUpScheduler, set_handler, set_starter_handler
from hunch.runtime import build_runtime, env_dir, load_env

log = logging.getLogger("hunch.telegram")
SEND_TIMEOUT_SECONDS = 60


def run() -> None:
    load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    admin = os.environ.get("TELEGRAM_ADMIN_USER_ID", "")
    if not token or not admin.lstrip("-").isdigit():
        raise SystemExit(
            "Set TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_USER_ID in .env (see .env.example)."
        )

    rt = build_runtime()
    data_dir = env_dir("HUNCH_DATA_DIR", "data")
    jobs_url = f"sqlite:///{(data_dir / 'jobs.sqlite').as_posix()}"
    loop_ref: dict[str, asyncio.AbstractEventLoop] = {}
    app_ref: dict[str, Application] = {}

    def send(chat_id: int, text: str) -> None:
        """Called from scheduler threads: hands the message to the bot's event loop."""
        future: Future = asyncio.run_coroutine_threadsafe(
            app_ref["app"].bot.send_message(chat_id=chat_id, text=text), loop_ref["loop"]
        )
        future.result(timeout=SEND_TIMEOUT_SECONDS)

    scheduler = FollowUpScheduler(jobs_url)
    channel = HunchChannel(
        rt.pipeline,
        ChannelStore(rt.pipeline.store.db),
        rt.cfg.initiative,
        send,
        admin_chat_id=int(admin),
        scheduler=scheduler,
        log_dir=env_dir("HUNCH_LOG_DIR", "logs"),
    )
    set_handler(lambda loop_id: channel.deliver_follow_up(loop_id))
    set_starter_handler(lambda: channel.starter_tick())
    scheduler.start()
    scheduler.every_hour_starters()
    for loop in rt.pipeline.loops.open_loops():  # re-arm follow-ups after a restart
        scheduler.schedule(loop.id, loop.follow_up_at)

    async def on_text(update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat is None or update.message is None or update.message.text is None:
            return
        reply = await asyncio.to_thread(
            channel.handle_message, update.effective_chat.id, update.message.text
        )
        await update.message.reply_text(reply)

    async def post_init(application: Application) -> None:
        loop_ref["loop"] = asyncio.get_running_loop()
        app_ref["app"] = application

    application = (
        Application.builder().token(token).post_init(post_init).build()
    )  # fmt: skip
    application.add_handler(MessageHandler(filters.TEXT, on_text))
    try:
        application.run_polling()
    finally:
        scheduler.shutdown()
        rt.store.close()


if __name__ == "__main__":
    run()
