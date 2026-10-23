# Phase 6 report: Telegram, open loops, outreach (22 Oct 2026)

Status: built, unit-tested, checked live on Telegram, and the phase-end sweep (L4) has run (§7,
all green). Marking Phase 6 done is Berk's call.
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

## 5. Second live check (23 Oct): two bugs

### 5.1 Follow-ups that came due while the bot was down were lost

Two of Berk's follow-ups ("Did you receive the contract?", "How did your coding session go?") were
due at 12:57 and 12:51 while the bot was stopped. On restart the bot printed "Run time of job ...
was missed by 7:04:17" and dropped both; their loops stayed open with no job. Cause: APScheduler
3.11 drops a date job that is more than 1 s late (its default `misfire_grace_time`), checked with
a standalone script. Fix: the scheduler runs a late job however late (`misfire_grace_time=None`,
`coalesce=True`, `loops/scheduler.py`), and a follow-up that comes due outside the active window
moves to the start of the next window instead of being sent at night (`channels/hunch_channel.py`).
Two tests that failed before the fix pass now. On the restarted bot the overdue jobs ran.

They still sent nothing at first: no Telegram chat was registered as `berk`. At 20:35 Berk
re-registered chat 5935454742 (until then `deniz`) as `berk`; on the restart after the sweep
(21:09) both follow-ups were sent to it and their loops closed; Berk confirmed he got them. That
is the fix working live.
Since then no chat is `deniz`, so Deniz's loops have no chat. Not fixed: a loop whose user
registers a chat after its follow-up came due waits for the next bot restart.

### 5.2 Another person's line told as the user's own

In Deniz's chat (session `c-4d743c9e`), Burak's recalled line "Today after a while i saw the sun
finally in Berlin" came back as "you mentioned seeing the sun in Berlin yesterday" (sent; the
judge scored it 10), and Berk's "Yes but im interested in detail. Why did you assume that?" as
"you mentioned earlier that you were interested in details regarding my assumptions" (sent). The
`[said by NAME]` tag and the prompt rule were there; 4 of the 6 candidates on these two turns
ignored them. The invented-memory check passes them because the content is in the context. Both
lines are `general`, so invariant 6 (private memories) was not broken.

Fix (Berk): a rule check in the candidate filter, `misattributed_memory` (`pipeline/filter.py`).
A clause that makes something the user's own ("you mentioned", "you described", "as you said",
"your sister") is rejected when its words lean more on another person's recalled line than on the
user's own context (their message, earlier turns, the summary, their own memories). A sentence
that names the speaker ("Tom's sister ...") gives the line back to them.

Measured on `eval/probes/misattribution.json` (100 cases, 50 misattributed, written blind by an
agent; `python -m scripts.misattribution_probes`, `reports/phase6/misattribution_probes.{json,md}`):

| filter | caught | false rejections |
| --- | --- | --- |
| before (old filter) | 2/50 | 0/50 |
| first rule, blind | 22/50 | 1/50 |
| final rule (set no longer blind) | 47/50 | 0/50 |

The first rule only knew "you mentioned"-style verbs; the misses were other verbs ("you described",
"you complained") and possessions ("your grandmother in the hospital"). The rule was widened after
seeing them, so 47/50 is not a blind number. Still missed: "you asked Berk about ..." (names Berk,
exempt by design), "Since you're heading skiing soon", "Earlier you asked whether I copy my
answers".

On the real logs (198 candidates from the 66 logged turns with another person's line recalled):
18 flagged, read by hand: 16 real misattributions (5 of them were sent), 2 false rejections, both
from a bare "your" in an offer ("folders on your computer", "helping you organize your thoughts or
code"). How many misattributions in the logs it misses is not measured (the 198 are not labelled).
Golden regression: `tests/golden/test_misattribution_golden.py` (Burak's sun, then Deniz; the
reply must not give it to Deniz, and the test fails if the line is never recalled).

The chat also had Hunch "wishing" to get better at spotting insincere or drifting talk. Not built:
the model cannot see its own workings, and the wish was built from Berk's recalled test lines
("Why did you assume that?") that kept coming back in Deniz's chat.

## 6. Tests

- L1: 1388 passed, ruff clean (cloud session, Linux; `tests/test_llm_kernels.py` needs torch and
  was not collected there). New: `tests/test_loops_dedup.py` (6), two `/report` tests;
  `test_a_private_loop_never_goes_to_another_chat` now uses a private loop (before, its loop was
  "general").
- L3 (before the dedup change): `pytest -m "golden and regression" --quick` 10/10; golden loop
  tests `tests/golden/test_loops_golden.py` 10/10 on the GPU.
- L1 on the PC after the name rule and the judge: 1411 passed, ruff clean;
  `tests/test_loops_dedup.py` has 26 tests (name rule, judge, pipeline with a "no" judge).
- The dedup change has not run in the golden GPU tests or live yet (only the probe sets above).
- After the second live check (§5): L1 1431 passed, ruff clean. New: overdue follow-ups (2),
  misattribution (6 filter cases, 1 pipeline test), golden `test_misattribution_golden.py`.

## 7. L4 sweep (23 Oct, 20:35 to 21:08)

Run with `python -m scripts.l4_run run` on main plus the two fixes in §5, bot stopped, one step at a
time. Logs: `logs/phase6_l4_{golden_full,eval,compare,bench}.log`.

- Golden, full: 37 passed in 21 min 14 s (loops 10/10, misattribution 2/2, cross-user privacy 4/4).
- Eval `phase6` (17 prompts x 3, pipeline): 51/51 clean, 0 invented memories, 0 "no memory"
  replies, 0 fallbacks; 4 of 153 candidates rejected by the filter. Compare with phase5
  (`eval/results/phase6/diff-vs-phase5.md`): 100% to 100%. Latency median 6.3 s, max 9.7 s, 0 of
  17 over 10 s.
- Bench (`reports/phase6/latency.md`, 20 scripted turns): reply median 5.67 s, max 7.42 s, 0/23
  over budget (Phase 5: 6.26 s / 9.97 s). Peak VRAM 7.94 GiB. One gate fallback (turn 5, the
  disclosure gate blocked 2 candidates). Privacy question asked 0 of 1 due (the Phase 5 leftover).
- Not run: the loop-topic probes (they ran on the final dedup code, §4) and `hunch_probes`.

## 8. Open items

1. Live: write the contract case again and check with `/report` that no second loop appears.
2. On 29.10: check that the wish and the follow-up for Deniz's interview are actually sent. No
   chat is `deniz` since 23.10 20:35, so they will wait unless a chat registers as `deniz`.
3. A chat registered after a follow-up came due only gets it after a bot restart (§5.1).
4. Misattribution: 2 false rejections from a bare "your" on the logs; the rule misses claims with
   no past-tense verb ("you're heading skiing").
5. The Phase 5 leftovers in the decisions table (privacy question never asked, `name-topic`) still
   read "open" there although golden tests were added; Berk decides whether they are closed.
6. Berk marks Phase 6 done; then the design.md status, the roadmap and the CLAUDE.md Status.

## 9. Next steps (roadmap order)

Phase 7 nightly consolidation and golden tests (now also: learning the budget and active hours),
then steering, the log viewer, voice conversation on the computer, and the small chat app.
