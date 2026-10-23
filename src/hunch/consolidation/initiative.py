"""Nightly step (Phase 7): learn each Telegram user's active window and initiative budget from
their message hours and their reactions to Hunch's proactive messages (`loops/learning.py`)."""

from __future__ import annotations

from hunch.channels.store import ChannelStore
from hunch.config import Config
from hunch.loops.learning import DAY, LearnedInitiative, learn
from hunch.memory.store import MemoryStore


def learn_initiatives(
    store: MemoryStore, channels: ChannelStore, cfg: Config, now: float
) -> list[LearnedInitiative]:
    """Learns and saves one profile per registered chat; returns them for the nightly report."""
    lc = cfg.initiative_learning
    since = now - max(lc.window_days, lc.budget_days) * DAY
    profiles = []
    for _, user in channels.chats():
        messages = store.user_messages(user, since)
        recent = [t for t, _ in messages if t >= now - lc.window_days * DAY]
        profile = learn(
            user, channels.initiative(user), recent, messages,
            channels.outreach_times(user, since), now, cfg.initiative, lc,
        )  # fmt: skip
        channels.save_initiative(profile)
        profiles.append(profile)
    return profiles
