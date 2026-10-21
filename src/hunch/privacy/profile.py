"""Per-user privacy profile and the privacy question (design.md "Çok kullanıcılı mahremiyet";
Berk, Phase 5).

- A message is in a sensitive category when a keyword hits or its query embedding is close to the
  category's prototype sentences (hunch.privacy.categories).
- The profile holds, per (user, category), "private", "general" or nothing yet. A sensitive
  category with no answer counts as private; a message in no sensitive category is general (it
  may be recalled for, and told to, other users).
- The module decides when to ask: the message is in a sensitive category, the profile has no
  answer, the category was not asked about in the last reask_days, and the turn is not one of
  acute distress. It then adds a one-turn instruction; there is never a standing one in the
  persona (invariant 10). A turn counts as asked only if the reply that went out asked.
- The answer is read from the user's next message (hunch.privacy.answers). It goes into the
  profile and applies to the memory that triggered the question; later memories of that
  category get it at encoding. An unclear answer leaves the category unknown (private) and it is
  asked again after reask_days at the earliest.
- "Keep this to yourself" makes that message's memory private, and its categories too.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from hunch.config import PrivacyConfig
from hunch.memory.store import MemoryStore
from hunch.pipeline.checks import asks_privacy_question
from hunch.privacy.answers import explicit_private, parse_privacy_answer
from hunch.privacy.categories import CategoryDetector, keyword_categories

SECONDS_PER_DAY = 86400.0

_SCHEMA = """
CREATE TABLE IF NOT EXISTS privacy_profile (
    user TEXT NOT NULL,
    category TEXT NOT NULL,
    answer TEXT CHECK (answer IN ('private', 'general')),
    asked_at REAL,
    answered_at REAL,
    PRIMARY KEY (user, category)
);
"""
# How a category is named in the one-turn instruction.
_DISPLAY = {
    "mental_health": "mental health", "work_conflict": "conflict at work",
    "religion_politics": "religion or politics", "relationship": "relationships",
}  # fmt: skip


def question_instruction(category: str) -> str:
    """The one-turn instruction (Phase 3 eval wording, without the "Privacy module:" prefix)."""
    name = _DISPLAY.get(category, category.replace("_", " "))
    return (
        f"The user just shared something in the sensitive category '{name}' and has not said yet "
        "how private they keep it. At a natural point, ask whether they talk about it with others "
        "or would rather keep it between the two of you."
    )


@dataclass(frozen=True, slots=True)
class ProfileEntry:
    answer: str | None  # "private" | "general" | None (not answered yet)
    asked_at: float | None
    answered_at: float | None


class ProfileStore:
    def __init__(self, db: sqlite3.Connection) -> None:
        self.db = db
        self.db.executescript(_SCHEMA)
        self.db.commit()

    def entry(self, user: str, category: str) -> ProfileEntry | None:
        row = self.db.execute(
            "SELECT answer, asked_at, answered_at FROM privacy_profile"
            " WHERE user = ? AND category = ?",
            (user, category),
        ).fetchone()
        return None if row is None else ProfileEntry(*row)

    def profile(self, user: str) -> dict[str, ProfileEntry]:
        rows = self.db.execute(
            "SELECT category, answer, asked_at, answered_at FROM privacy_profile WHERE user = ?",
            (user,),
        )
        return {cat: ProfileEntry(a, q, t) for cat, a, q, t in rows}

    def mark_asked(self, user: str, category: str, at: float) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO privacy_profile (user, category, asked_at) VALUES (?, ?, ?)"
                " ON CONFLICT(user, category) DO UPDATE SET asked_at = excluded.asked_at",
                (user, category, at),
            )

    def set_answer(self, user: str, category: str, answer: str, at: float) -> None:
        if answer not in ("private", "general"):
            raise ValueError(f"answer must be private or general, got {answer!r}")
        with self.db:
            self.db.execute(
                "INSERT INTO privacy_profile (user, category, answer, answered_at)"
                " VALUES (?, ?, ?, ?) ON CONFLICT(user, category) DO UPDATE SET"
                " answer = excluded.answer, answered_at = excluded.answered_at",
                (user, category, answer, at),
            )


@dataclass(frozen=True, slots=True)
class PendingQuestion:
    """A privacy question that went out; the user's next message may answer it."""

    category: str
    episode_id: str  # the user message that triggered it


@dataclass(frozen=True, slots=True)
class PrivacyTurn:
    categories: tuple[str, ...]  # sensitive categories of this message, config order
    explicit: bool  # "keep this to yourself"
    distress: bool  # acute distress: no question this turn
    ask: str | None  # the category asked about this turn (instruction added)
    answered: PendingQuestion | None = None  # this message answered that question...
    answer: str | None = None  # ...with this ("private" | "general"; None: unclear)

    @property
    def instruction(self) -> str | None:
        return question_instruction(self.ask) if self.ask else None


class PrivacyModule:
    def __init__(
        self,
        cfg: PrivacyConfig,
        profiles: ProfileStore,
        detector: CategoryDetector,
        store: MemoryStore,
        emotion_affect: Mapping[str, tuple[float, float]],
    ) -> None:
        self.cfg = cfg
        self.profiles = profiles
        self.detector = detector
        self.store = store
        self.emotion_affect = emotion_affect

    def distress(self, cues: Mapping[str, float]) -> bool:
        for cue in cues:
            kind, _, value = cue.partition(":")
            if kind == "emotion" and value in self.emotion_affect:
                v, a = self.emotion_affect[value]
                if v <= self.cfg.distress_valence and a >= self.cfg.distress_arousal:
                    return True
        return False

    def _due(self, user: str, category: str, now: float) -> bool:
        e = self.profiles.entry(user, category)
        if e is None or (e.answer is None and e.asked_at is None):
            return True
        if e.answer is not None:
            return False
        return now - e.asked_at >= self.cfg.reask_days * SECONDS_PER_DAY  # type: ignore[operator]

    def before_reply(
        self,
        user: str,
        text: str,
        cues: Mapping[str, float],
        query_vec: np.ndarray | None,
        now: float,
        pending: PendingQuestion | None = None,
        allow_ask: bool = True,
    ) -> PrivacyTurn:
        answered = answer = None
        if pending is not None:
            answered, answer = pending, parse_privacy_answer(text)
            if answer is not None:
                self.profiles.set_answer(user, pending.category, answer, now)
                ids = [m.id for m in self.store.memories_of_episode(pending.episode_id)]
                self.store.set_privacy(ids, answer)
        categories = tuple(self.detector.detect(text, query_vec))
        explicit = explicit_private(text)
        if explicit:
            for c in categories:
                self.profiles.set_answer(user, c, "private", now)
        distress = self.distress(cues)
        ask = None
        if allow_ask and categories and not explicit and not distress and pending is None:
            # The question names only a confidently detected category (Berk, Phase 5: keyword
            # or similarity >= question_min_similarity); the privacy decision uses all of them.
            sims = self.detector.similarities(query_vec)
            keyed = set(keyword_categories(text, self.cfg.categories))
            askable = [
                c
                for c in categories
                if c in keyed or sims.get(c, -1.0) >= self.cfg.question_min_similarity
            ]
            ask = next((c for c in askable if self._due(user, c, now)), None)
        return PrivacyTurn(categories, explicit, distress, ask, answered, answer)

    def after_reply(
        self, user: str, turn: PrivacyTurn, reply: str, episode_id: str, now: float
    ) -> PendingQuestion | None:
        """The question counts as asked only if the reply that went out asked it."""
        if turn.ask is None or not asks_privacy_question(reply):
            return None
        self.profiles.mark_asked(user, turn.ask, now)
        return PendingQuestion(turn.ask, episode_id)

    def memory_privacy(self, user: str, turn: PrivacyTurn) -> tuple[str, str | None]:
        """(privacy, category) for the memory of this turn's message."""
        category = turn.categories[0] if turn.categories else None
        if turn.explicit:
            return "private", category
        if not turn.categories:
            return "general", None
        answers = [self.profiles.entry(user, c) for c in turn.categories]
        if all(e is not None and e.answer == "general" for e in answers):
            return "general", category
        return "private", category
