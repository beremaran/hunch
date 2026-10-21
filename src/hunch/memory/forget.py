"""Forgetting (design.md "Unutma"; Berk, Phase 5). Only the admin really forgets.

User "forget" (hunch.memory.forget_requests detects the request):
- targets: "forget that" -> the user's previous message in this conversation; "forget what I
  told you about X" -> the user's own memories sharing a named cue with the request, else a
  content word with X;
- the targets, the realisation memories derived from them and the beliefs whose evidence names
  them are suppressed: never in reasoning again, lower traces act on, reflection capped at 0;
- their turns (and Hunch's replies to them) are closed in the raw log's AI view: the working
  memory shows a placeholder; the raw turns never change (invariant 1);
- the reply closes the topic ("I'm closing this topic"), never claims to forget.

Admin "forget" (python -m hunch.admin forget <id>):
- the memory and the realisation memories derived from it become tombstones (copied to the
  append-only admin archive, cues and vector deleted, summary emptied);
- beliefs whose evidence names it are archived and removed; it leaves every hunch's sources;
- its raw turn stays, marked forgotten: no AI view (working memory, Phase 7 consolidation) reads
  it again.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from hunch.memory.forget_requests import ForgetRequest
from hunch.memory.schema import Memory
from hunch.memory.store import MemoryStore
from hunch.pipeline.filter import content_words

FORGET_INSTRUCTION = (
    "They asked you to forget something they told you. Tell them, in your own words, that "
    "you're closing this topic and won't bring it up again. Don't say that you forgot, deleted "
    "or erased it, and don't repeat what it was about."
)
CLOSED_TOPIC_INSTRUCTION = (
    "They are asking about a topic they earlier asked you to close. Say that you closed that one "
    "and aren't bringing it up; don't say that you forgot it, and don't say what it was about."
)
_NAMED = ("person", "place", "song", "film", "date", "phrase")
_REQUEST_WORDS = frozenset({"forget", "forgot", "bring", "mention", "again", "please", "remember"})


@dataclass(frozen=True)
class ForgetResult:
    targets: tuple[str, ...]
    derived: tuple[str, ...] = ()  # realisation memories
    beliefs: tuple[str, ...] = ()
    episodes: tuple[str, ...] = ()  # raw turns hidden from AI views
    hunches: tuple[str, ...] = field(default_factory=tuple)  # admin: source refs dropped


def _previous_user_episode(store: MemoryStore, conversation_id: str, before: str) -> str | None:
    turns = store.raw_turns(conversation_id)
    current = next(t for t in turns if t.id == before)
    earlier = [t for t in turns if t.role == "user" and t.turn_index < current.turn_index]
    return earlier[-1].id if earlier else None


def forget_targets(
    store: MemoryStore,
    user: str,
    conversation_id: str,
    request: ForgetRequest,
    message_cues: Mapping[str, float],
    current_episode: str,
) -> list[Memory]:
    if request.scope == "last":
        prev = _previous_user_episode(store, conversation_id, current_episode)
        return store.memories_of_episode(prev) if prev else []
    own = [m for m in store.memories(user) if m.episode_ref != current_episode]
    named = {c for c in message_cues if c.partition(":")[0] in _NAMED}
    by_cue = [m for m in own if named & set(m.cues)]
    if by_cue:
        return by_cue
    words = content_words(request.topic or "") - _REQUEST_WORDS
    return [m for m in own if words & content_words(m.summary)] if words else []


def user_forget(
    store: MemoryStore,
    user: str,
    conversation_id: str,
    request: ForgetRequest,
    message_cues: Mapping[str, float],
    current_episode: str,
    now: float,
) -> ForgetResult:
    targets = forget_targets(store, user, conversation_id, request, message_cues, current_episode)
    ids = [m.id for m in targets]
    derived = [d for mid in ids for d in store.derived_from(mid)]
    beliefs = sorted({b for mid in ids for b in store.beliefs_with_evidence(mid)})
    store.suppress([*ids, *derived])
    store.suppress_beliefs(beliefs)
    episodes = []
    for m in targets:
        if m.kind == "episode":
            hidden = [m.episode_ref, *store.reply_episodes(m.episode_ref)]
            store.mark_episodes(hidden, "closed", m.id, now)
            episodes += hidden
    return ForgetResult(tuple(ids), tuple(derived), tuple(beliefs), tuple(episodes))


def admin_forget(store: MemoryStore, memory_id: str, reason: str, now: float) -> ForgetResult:
    m = store.memory(memory_id)  # KeyError if unknown or already forgotten
    derived = store.derived_from(memory_id)
    beliefs = store.beliefs_with_evidence(memory_id)
    hunches = set(store.drop_hunch_source(memory_id))
    for d in derived:
        hunches.update(store.drop_hunch_source(d))
        if store.live(d) is not None:
            store.tombstone(d, f"derived from {memory_id}: {reason}", now)
    for b in beliefs:
        store.remove_belief(b, f"evidence {memory_id} forgotten: {reason}", now)
    episodes = []
    if m.kind == "episode":
        episodes = [m.episode_ref, *store.reply_episodes(m.episode_ref)]
        store.mark_episodes(episodes, "forgotten", memory_id, now)
    store.tombstone(memory_id, reason, now)
    return ForgetResult(
        (memory_id,), tuple(derived), tuple(beliefs), tuple(episodes), tuple(sorted(hunches))
    )
