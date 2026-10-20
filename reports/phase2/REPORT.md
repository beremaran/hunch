# Phase 2 report: memory store and activation engine (20 Oct 2026)

Status: all five steps built and tested. Not committed yet (waiting for Berk's review).
Checks on the final state: ruff check + format clean; `pytest` 323 passed; `pytest -m "golden or slow"` 14 passed; eval `phase2` vs `phase1c`: no change (94% clean, 0 invented memories, max 6.6 s per batched call).

## 1. Storage (`src/hunch/memory/`)
- `store.py`: SQLite + sqlite-vec (cosine). Tables: `episodes` (raw turns, append-only, enforced by DB triggers), `memories` (`owner_user`, `privacy` required), `memory_cues` (fan counts, also counted in context), `memory_access` (append-only recall log), `memory_affect_log` (append-only: encoded affect first, then every reconsolidation), `memory_vec`.
- The store refuses a database inside `core/` and any file that is not `.db`/`.sqlite` (so never `.env`); it is on the reviewed file-writer list of `tests/test_no_core_writes.py`.
- `select_working_memory`: newest turns verbatim within N = 10 turns and ~2,000 tokens (config), older turns returned for the session summary; the newest turn is always kept. Phase 3 builds working memory on this.
- `embeddings.py`: Qwen3-Embedding-0.6B on CPU (no VRAM), last-token pooling, instruction on queries only. Test `-m slow`: related memory ranks first.

## 2. Activation engine (`src/hunch/recall/activation.py`, pure functions)
A = B + α·arousal·salience + Σ W_c·bond·max(m, S − ln fan_c|context) + μ·cos(mood, affect) + ε

Decisions by Berk during the phase (all in the design.md decisions table):
- A recall refreshes a memory to ~90% of a new memory (`refresh_strength = 0.9`); recalls do not stack; then it fades. (The ACT-R sum is kept as `rehearsal = "accumulate"` for comparison only.)
- Fan is counted in context ("Anna" + "sailing" is rare for the sailing memory), and every shared cue adds at least m = 0.2.
- Bond strength multiplies spreading; mood congruence uses (valence, arousal − 0.5); a suppressed memory is capped at the lower layer.
- Approved values: d 0.5, t in days (floor 1 h), α 3.0, S 3.0, m 0.2, μ 0.5, noise 0.25, τ_upper −0.5, τ_lower −1.5, cue weights person = song 1.0, film 0.8, place 0.7, phrase = date 0.6, emotion 0.4, at most 3 memories enter reasoning per turn.

## 3. Simulation (`scripts/simulate_recall.py`, plots in this folder)
50 hand-written memories over 6 months, daily conversations with realistic cue rates. All checks pass and run as tests (`tests/test_simulate_recall.py`):
- (a) always recalled: the 3 flashbulbs + 3 strong life events (job interview, a new baby, a dog); no trivial memory locks in.
- (b) the 3 song memories only come back with their song.
- (c) a song adds +2.7, the frequent name only the minimum.
- (d) Berk's sailing example: "Anna" alone A = −0.68 (not recalled), "Anna" + "sailing" A = +2.73; the name's own term rises from 0.14 to 2.1.
- Rehearsal is bounded (saw-tooth, max ≈ 2.9 instead of climbing to 4.7).

## 4. Cue extraction (`src/hunch/recall/cues.py`, `dates.py`)
- The LLM returns JSON; every cue is validated and normalised ("type:value", accents stripped); fixed emotion vocabulary; invalid items dropped with a reason; one retry, never a crash.
- The LLM only finds date expressions; `dates.py` resolves them in code (weekdays, "last Sunday", "in two days", "March 3rd" → next occurrence, holidays as names).
- Role words are not persons ("my mum", "little brother", "cousins").
- Two blind label sets written by a separate agent: `eval/cues/labelled.json` (30 messages, tuning) and `eval/cues/heldout.json` (20 messages, measured once).

| set | precision | recall |
| --- | --- | --- |
| tuning set, first prompt | 79% | 69% |
| tuning set, final | 92% | 81% |
| **held-out (the number to report)** | **83%** (lenient 87%) | **69%** (lenient 72%) |

Held-out per type: person, place, song 100/100; film 75/100; date 100/38; emotion 73/62; phrase 0/0 (1 gold item, lenient match). Latency ~2.6 s per message on the 9B model.

## 5. Involuntary recall and reconsolidation
- `involuntary.py`: a memory is involuntary when it crosses τ_upper only thanks to the message's cues and was not retrieved on purpose; per-session cap; suppressed memories never qualify.
- `reconsolidation.py`: each recall logs an access and drifts the memory's affect toward the current mood; the raw episode never changes and the original encoding stays in the affect log.

## Open items
1. ~~Two parameters still PROPOSED~~ Approved by Berk: `involuntary_per_session = 1`, `reconsolidation_rate = 0.1`.
2. **Date recall 38% on held-out**: the model often does not report the date expression at all. Proposal: a rule-based date-expression finder in code next to the LLM (same resolver), measured on a *new* held-out set (the current one is used up).
3. **Latency for Phase 3**: cue extraction (~2.6 s) + 3 batched candidates (~4–6 s) + value-gate judge will be tight against 10 s. Options to evaluate in Phase 3: shorter extraction output, running extraction while the previous turn's work finishes, or extracting cues in the same call as the reasoning.
4. Phrase cues are rare and weak (0/2 on tuning, 1 lenient on held-out); low priority.
