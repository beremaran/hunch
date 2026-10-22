# Phase 6 report: Telegram, open loops, outreach (22 Oct 2026)

Status: built, unit-tested and checked live on Telegram. Marking Phase 6 done is Berk's call.
The design is in `docs/design.md` ("Açık döngüler ve proaktivite"); every decision below is in its
decisions table.

## 1. Decisions (all in the design.md decisions table)

| Topic | Decision |
| --- | --- |
| End of a Telegram conversation | 30 minutes without a message; the summary folds, session state resets, long-term memory stays |
| Summary fold delay | The fold waits while a message is queued; only the last queued message folds |
| Initiative budget | At most 2 messages per user per day that Hunch writes first (follow-ups and starters share it) |
| Timed event | A wish 1 hour before the event, a "how did it go?" 2 hours after it, both moved into the active window |
| Conversation starters | Small talk or curious questions; a starter recalls nothing and claims no experience of its own |
| Private loops | No extra disclosure gate: a follow-up only goes to the loop owner's own chat (test-guarded) |
| Learning the budget and active hours | Deferred to Phase 7 (nightly consolidation); Phase 6 keeps 2/day and 9-22 |
| One loop per matter | Added after the live check, see §4 |

## 2. What was built

- `loops/`: open-loop store (`store.py`), extraction from each user message after the reply, so it
  adds no latency (`extract.py`, a rule-based date finder resolves the weekday, the model is bad at
  weekday arithmetic), the budget and active window (`budget.py`), persistent follow-up jobs that
  survive a restart (`scheduler.py`, APScheduler with a SQLite job store), outreach texts for
  follow-ups and starters (`outreach.py`), and one loop per matter (`dedup.py`, new).
- `channels/`: the channel-agnostic `HunchChannel` (conversations, owner-only delivery, starters,
  admin commands `/forget`, `/logs`, `/report`) and the Telegram adapter.
- Outreach runs through the same candidate filter, judge and value gate as a reply.
- Persona rewrite: honest, calm, lightly humorous; no gushing, no talk of its own feelings, brief
  answers to "are you there?". Gushing words removed from the drive warmth lexicon.
- `/report` lists the open loops (time, owner, privacy, topic, planned question), soonest first,
  at most 10. Before, it only gave their number, so a timed event could not be checked live.
- Phase 5 leftovers: the cue prompt counts names in questions too, and two golden tests
  (`tests/golden/test_privacy_question.py`, `tests/golden/test_cue_questions.py`), commit `0c94e36`.

## 3. Live check on Telegram (22 Oct, Berk)

Three users, a fresh chat, after restarting the bot with the persona changes.

| Check | Result |
| --- | --- |
| "Are you there?" | Calm, brief |
| The same message twice | Different replies, no copy |
| Several quick messages | One reply per message, consistent |
| Tone | Hardly cynical; a light mischief is noticeable, Berk liked it |
| Terminal | No errors or warnings |
| Starter | Hunch wrote first once: a question about coffee beans. Recalled nothing, as designed |
| Timed event "My interview is on Thursday at 2pm" | Two loops: wish Thu 29.10 13:00, follow-up Thu 29.10 16:00 |

The message was sent on Thursday 22.10, so "Thursday" resolved to the next Thursday. The
follow-ups themselves were not waited for; they are due on 29.10.

## 4. Finding from the live check: two loops for one matter

The open loops (read from the database) held two loops for the same contract:
"Did you receive the contract?" (23.10) and "How did it go with getting your new contract?"
(27.10). Extraction had no duplicate check, so Hunch would have asked twice.

Fix (Berk, option A): a new draft whose topic embedding is at least `same_topic_similarity`
(cosine) to an open loop of the same user is dropped; two drafts of one message are deduplicated
the same way. A new timed event replaces the old loops (the old ones are closed; a job already
scheduled for them finds them closed and sends nothing), so a moved interview gets the new time.
No extra model call. Without an embedder only exact topics match. Another user's loops never count.

The threshold 0.75 is not measured yet. The cloud session that built this could not download the
embedding model. A blind probe set was written by an agent that saw no code:
`eval/probes/loop_topics.json`, 60 pairs (30 the same matter, 30 different, 15 of them hard
negatives from the same domain). Measure on the PC:

```
.venv\Scripts\python.exe -m scripts.loop_topic_probes
```

It writes `reports/phase6/loop_topic_probes.{json,md}`: a sweep 0.60-0.90 with same-matter pairs
caught and different pairs merged. A lost loop costs more than a repeated question, so the
threshold should merge no different pair.

## 5. Tests

- L1: 1388 passed, ruff clean (cloud session, Linux; `tests/test_llm_kernels.py` needs torch and
  was not collected there). New: `tests/test_loops_dedup.py` (6), two `/report` tests;
  `test_a_private_loop_never_goes_to_another_chat` now uses a private loop (before, its loop was
  "general").
- L3 (before the dedup change): `pytest -m "golden and regression" --quick` 10/10; golden loop
  tests `tests/golden/test_loops_golden.py` 10/10 on the GPU.
- The dedup change has not run on the GPU or live yet.

## 6. Open items

1. Measure the dedup threshold (§4) and set it in `config/hunch.toml`.
2. Live: write the contract case again and check with `/report` that no second loop appears.
3. On 29.10: check that the wish and the follow-up for the interview are actually sent.
4. The phase-end sweep (L4: full golden, `eval.run_eval --tag phase6 --pipeline`,
   `eval.compare`, bench) has not run for Phase 6.
5. The Phase 5 leftovers in the decisions table (privacy question never asked, `name-topic`) still
   read "open" there although golden tests were added; Berk decides whether they are closed.

## 7. Next steps (roadmap order)

Phase 7 nightly consolidation and golden tests (now also: learning the budget and active hours),
then steering, the log viewer, voice conversation on the computer, and the small chat app.
