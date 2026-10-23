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

Measured on the PC (`python -m scripts.loop_topic_probes`, `--set 2`):

- Set 1 (`eval/probes/loop_topics.json`, 60 pairs, blind): at 0.75, 18/30 same-matter pairs caught
  and 2/30 different pairs merged; the closest different pair was "flight to Berlin" / "flight to
  Madrid" (0.916), so no threshold merged none and still caught repeats.
- Berk chose a name rule plus 0.80: two topics that both name someone or somewhere (capitalised
  words) with no name in common never merge (`loops/dedup.py`, `distinct_names`). A capitalised
  word the other topic has in lower case ("Dinner" / "dinner") does not count as a name. Set 1 is
  no longer blind after this: 14/30 caught, 0/30 merged at 0.80.
- Set 2 (`eval/probes/loop_topics2.json`, 80 pairs, 40 different, written blind after the rule
  was chosen, with many pairs that differ only by a name): first rule version (first word never a
  name) at 0.80: 27/40 caught, 5/40 merged (two of them "Chelsea match" / "Liverpool match",
  "Lakers game" / "Celtics game"). The rule was then changed to count a capitalised first word;
  set 2 is no longer blind after that: 27/40 caught, 3/40 merged.

| threshold | set 1 caught | set 1 merged | set 2 caught | set 2 merged |
| --- | --- | --- | --- | --- |
| 0.75 | 18/30 | 1/30 | 32/40 | 9/40 |
| 0.80 | 14/30 | 0/30 | 27/40 | 3/40 |
| 0.85 | 8/30 | 0/30 | 17/40 | 1/40 |
| 0.90 | 2/30 | 0/30 | 9/40 | 0/40 |

The three set 2 pairs still merged at 0.80 differ by a common noun, not a name: "renting a flat" /
"buying a flat" (0.876), "knee pain" / "back pain" (0.824), "math exam" / "physics exam" (0.800).
The embedding cannot tell these apart; only a threshold of 0.90 merges none, and it catches few
repeats. Reports: `reports/phase6/loop_topic_probes{,2}.{json,md}`.

Model judge (Berk): a pair at or above the threshold merges only when a short greedy yes/no call
says it is the same matter (`SAME_MATTER_PROMPT` in `loops/dedup.py`; only a clear "yes" merges;
identical topics merge without a call; the judge runs after the reply, so it adds no latency).
Measured with `--judge` (`reports/phase6/loop_topic_probes{,2}_judge.{json,md}`):

| threshold | set 1 caught | set 1 merged | set 2 caught | set 2 merged |
| --- | --- | --- | --- | --- |
| 0.60 | 29/30 | 0/30 | 38/40 | 0/40 |
| 0.65 | 26/30 | 0/30 | 37/40 | 0/40 |
| 0.70 | 24/30 | 0/30 | 34/40 | 0/40 |
| 0.75 | 18/30 | 0/30 | 30/40 | 0/40 |
| 0.80 | 14/30 | 0/30 | 25/40 | 0/40 |

The judge alone was right on 59/60 and 78/80 pairs; every error was on the safe side (a repeat
kept, no loop lost): "apartment deposit" / "getting the security deposit back", "Spotify offer" /
"job offer from Spotify", "Anna's birthday" / "Anna's birthday gift". With the judge, no threshold
from 0.60 up merged a different pair, so the threshold now only sets how many pairs reach the
judge. Caveat: the judge prompt names the kinds of differences seen in these sets (renting vs
buying, body parts, subjects), so neither set is blind for the judge.

Set 3 (`eval/probes/loop_topics3.json`, 100 pairs, 50 the same matter, 35 hard negatives), written
blind after the judge prompt was fixed (`reports/phase6/loop_topic_probes3_judge.{json,md}`):

| threshold | 0.55 | 0.60 | 0.65 | 0.70 | 0.75 | 0.80 |
| --- | --- | --- | --- | --- | --- | --- |
| same matter caught | 48/50 | 48/50 | 46/50 | 42/50 | 36/50 | 30/50 |
| different pairs merged | 0/50 | 0/50 | 0/50 | 0/50 | 0/50 | 0/50 |

The judge alone was right on 99/100; its one error was on the safe side ("visa application" /
"visa appointment" kept apart). The closest different pairs it kept apart: "dog's vet checkup" /
"cat's vet checkup" (0.925), "camping trip with Jonas" / "hiking trip with Jonas" (0.917), "Tom
and Laura's wedding" / "Tom and Sara's wedding" (0.890). Across all three sets, from 0.60 up, no
different pair merged; 0.60 catches 29/30, 38/40 and 48/50 repeats. Lower than 0.60 adds nothing
on set 3 and only sends more pairs to the judge. Berk set the threshold to 0.60
(`config/hunch.toml`).

## 5. Tests

- L1: 1388 passed, ruff clean (cloud session, Linux; `tests/test_llm_kernels.py` needs torch and
  was not collected there). New: `tests/test_loops_dedup.py` (6), two `/report` tests;
  `test_a_private_loop_never_goes_to_another_chat` now uses a private loop (before, its loop was
  "general").
- L3 (before the dedup change): `pytest -m "golden and regression" --quick` 10/10; golden loop
  tests `tests/golden/test_loops_golden.py` 10/10 on the GPU.
- L1 on the PC after the name rule and the judge: 1411 passed, ruff clean;
  `tests/test_loops_dedup.py` has 26 tests (name rule, judge, pipeline with a "no" judge).
- The dedup change has not run in the golden GPU tests or live yet (only the probe sets above).

## 6. Open items

1. Dedup (§4): name rule, model judge, threshold 0.80; 0 different pairs merged on both sets
   with the judge. Blind set 3 for the judge: 99/100, 0 merged at any threshold.
   Berk set 0.60 (48/50 repeats caught). Not yet run live or in the GPU golden tests.
2. Live: write the contract case again and check with `/report` that no second loop appears.
3. On 29.10: check that the wish and the follow-up for the interview are actually sent.
4. The phase-end sweep (L4: full golden, `eval.run_eval --tag phase6 --pipeline`,
   `eval.compare`, bench) has not run for Phase 6.
5. The Phase 5 leftovers in the decisions table (privacy question never asked, `name-topic`) still
   read "open" there although golden tests were added; Berk decides whether they are closed.

## 7. Next steps (roadmap order)

Phase 7 nightly consolidation and golden tests (now also: learning the budget and active hours),
then steering, the log viewer, voice conversation on the computer, and the small chat app.
