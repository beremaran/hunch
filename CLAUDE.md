# Hunch — AI Memory Consciousness System

A local AI with a human-like memory: it remembers, forgets, learns from experience, changes its mind, takes initiative and follows up on open topics. One shared personality talks to several users over Telegram.

**Source of truth:** `docs/design.md` in this repo (Turkish); there is no external live version. Read it before any design-relevant change. The decisions table in that file lists what Berk (owner/admin) decided and what is only a default proposed by Claude.

**Status:** Phases 0–4 done (Phase 3: turn pipeline as a local CLI chat; Phase 4: Hunch only when modulation materially changes the choice, flag only when the user asks why, graded reflection 0–3 with realisation memories, beliefs and weakened traces, admin-only reflection log; see `reports/phase4/REPORT.md`). Phase 5 (mood, multi-user privacy, forgetting) is built, unit-tested (L1: 1312 passed), committed (`ae2b2d9`), and its phase-end sweep has run (golden, eval, bench, probes; results in `reports/phase5/REPORT.md` §10). Marking it done is Berk's call. Global mood + per-user relationship (`mood/`); privacy profile, sensitive categories, and the privacy question as a one-turn instruction, only on a turn where the user says they want to tell someone about a sensitive topic (keyword rule `shares_with_others`), at most once per user per 7 days, "infer first, ask rarely" (`privacy/`); mediation (other users' private memories act only from below) and the disclosure gate (`values/gate.py`); cross-user leak check in `tests/leak_check.py`; user forget = suppress + close turns, admin forget = tombstone + admin archive (`memory/forget.py`, `python -m hunch.admin`). A plain-language overview for outside readers is in `docs/STORY.md`. Work follows the MVP roadmap at the end of `docs/design.md`. Step-by-step prompts are in `docs/claude-code-prompts.md`.

## Environment

- Windows PC, NVIDIA RTX 4070 Ti Super (16 GB VRAM), 32 GB RAM. Project root: `C:\hunch`.
- Python 3.12, PyTorch + CUDA, Hugging Face transformers.
- Native Windows, no WSL2 (decided). Main model: `Qwen/Qwen3.5-9B`, 4-bit (bitsandbytes NF4); it stays. Gated DeltaNet fast path: `flash-linear-attention` + `triton-windows`; `causal-conv1d` has no Windows build and is not needed (<1% of GPU time). Bigger models are only a later option.
- Embeddings: `Qwen/Qwen3-Embedding-0.6B` (CPU is fine if VRAM is tight).
- Storage: SQLite + sqlite-vec. Scheduler: APScheduler. Channel: Telegram bot.
- Before installing anything system-wide (CUDA toolkit, WSL, drivers), ask first.

## Product rules

- **Language:** Hunch speaks English only. If a user writes in another language, it replies in English and says it only speaks English. Phase 3 adds a simple "is the input English?" check and rejects reply candidates that contain CJK characters, are not in English, claim a memory not in context or describe Hunch as having no memory (another of the 3 candidates is picked; if all 3 fail, the fixed reply "I don't have that in mind right now. Could you tell me again?" is sent). German and Turkish are out of scope for the AI (Berk himself may still write to Claude in Turkish, German or English).
- **Working memory:** the last N turns of the current conversation verbatim plus a rolling session summary are always in the reasoning context, in their own block, separate from recalled memories. Limits: N = 10 turns and ~2,000 tokens; when either is hit, the oldest turns move into the session summary. Both live in config (`config/hunch.toml`).
- **Latency budget:** ≤ 10 s per Telegram reply on this GPU. Reply candidates are generated in one batched call (`num_return_sequences`), never one after another.

## Invariants (never break these)

1. **Raw episodic log is append-only.** Never update or delete raw records. A user "forget" only marks a memory `suppressed`. An admin "forget" removes the memory and its derived beliefs and lower traces from AI-visible stores; the raw record stays in an admin-only archive.
2. **The lower layer never reaches the prompt as content.** Lower traces, the drive vector and modulation logs must never appear in any model prompt. The only things allowed through: the hunch flag (valence, intensity) and a coarse mood label.
3. **No write path to core values or `.env`.** `core/values.yaml` is loaded read-only with a strict schema check at startup; if it is missing or invalid the system refuses to start (fail-closed). No code path in `src/` may write to `core/` or to `.env` (`tests/test_no_core_writes.py`). The AI can only create an `AmendmentProposal` for Berk to review. Signing is deferred (Berk will specify a more usable scheme later); do not reintroduce it without asking.
4. **Order of the turn:** reasoning → candidates → modulation → value gate → reply. The value gate is always last.
5. **Quality floor:** modulation only chooses among candidates above the quality threshold.
6. **Cross-user privacy:** a user's `private` memories must never appear in, or be hinted at by, a reply to another user. The disclosure check is rule-based plus a model judge, never the model judge alone.
7. **Admin sees everything, the AI sees none of its own modulation.** Every internal decision is logged for the admin; raw logs are never fed back to the AI. Berk (decided in Phase 5, built in Phase 7): the nightly job may derive insights from the logs, only from a strong and repeated pattern, as plain text at most at reflection level, stored as Hunch's own memory; never numbers, ids, drive values or other users' private sources (design.md, "Kendi loglarından öğrenme").
8. **Multi-user from day one:** every memory carries `owner_user` and `privacy`.
9. **Memories come only from the pipeline.** The persona prompt never encourages the model to bring up remembered topics on its own and tells it it remembers nothing beyond what the context shows. The invented-memory check stays in `eval/` and in `tests/golden/` as a permanent regression test (since Phase 3 on the pipeline output: 0 invented memories and 0 "I have no memory"-style replies allowed).
10. **The privacy module decides when to ask about privacy.** It injects a one-turn instruction; there is never a standing "ask whether this is private" instruction in the persona prompt.
11. **Do not do everything on your own**, delegate to sub agents when needed. Choose models based on the task complexity.

## Conventions

- Code, identifiers, comments and commit messages in English. `docs/design.md` stays in Turkish; when a decision changes, update its decisions table.
- Type hints everywhere, `pytest` for tests, `ruff` for lint and format.
- All tunable parameters (activation d, α, μ, S, noise, thresholds τ_upper/τ_lower, decay rates, mood leak, initiative budget, candidate count, quality floor) live in one config file, not hardcoded.
- Randomness (recall noise, exploration, reflection) goes through a seedable RNG so tests are deterministic.
- Keep GPU work behind one `llm` module so the model can be swapped (see the upgrade path in the design doc).
- Secrets (Telegram token, admin ID, key paths) in `.env`, never committed.
- `eval/` is a regression suite (English, 3 sampled replies per prompt; German, Turkish and French inputs only as language probes). Re-run it at the end of every phase (`python -m eval.run_eval --tag phaseN`) and report the diff against the previous baseline (`python -m eval.compare <old> <new>`).
- Golden tests in `tests/golden/` need the GPU and the model; run them with `pytest -m golden` (excluded from the default run).

## Test levels

GPU runs are the slow part (golden ~8 min, eval ~10 min, bench and probes a few each). Don't run everything for every change; use the smallest level that covers it:

| Level | When | Command | Time |
| --- | --- | --- | --- |
| L1 unit | every change | `.venv/Scripts/python -m pytest -q` (CPU only) | ~25 s |
| L2 area | while building a feature | `pytest -q -m "<area> and not golden"` (areas: values, memory, recall, pipeline, hunch, honesty, evalset, infra); a bare `-m <area>` also runs that area's golden GPU tests | seconds |
| L3 regression | a feature is done | `pytest -m "golden and regression" --quick` plus the feature's own GPU tests/probes | a few min |
| L4 phase end | once per phase, before the report | `pytest -m golden`, `python -m eval.run_eval --tag phaseN --pipeline`, `eval.compare`, the bench, the phase's probes | ~30+ min |

- Every test file is mapped to one area in `tests/conftest.py` (`AREAS`); `tests/test_test_levels.py` fails if a new file is missing.
- The L3 set is marked `regression` inside the golden tests (a few safety-critical cases: honesty probes, asked-why); `--quick` uses their small run counts. Add a case when a new behaviour must never regress.
- GPU jobs run in the background, one at a time.


## Target layout

```
src/hunch/
  config.py
  llm/            # model loading, generation, steering hooks
  values/         # signed values loader, AmendmentProposal, value gate
  memory/         # working memory, episodic store, Memory schema, embeddings
  recall/         # cue extraction, activation engine, involuntary recall
  drive/          # drive vector, modulation, Hunch
  reflection/     # graded hunch reflection
  mood/           # global mood, per-user relationship state
  privacy/        # privacy profiles, disclosure gate
  loops/          # open loops, initiative budget, scheduler
  consolidation/  # nightly job
  channels/       # telegram
  observability/  # turn, reflection, revision, disclosure logs; nightly report
  pipeline/       # turn pipeline: language check, prompt, candidate filter, orchestration
  runtime.py      # wires real components (paths from .env); cli.py: local chat
  admin.py        # admin commands: find, forget (admin "forget"), archive
core/             # values.yaml (read-only at runtime)
tests/  tests/golden/
scripts/  eval/
data/  logs/      # gitignored
```

## Working with Berk

- Berk is a test architect: he values tests, measurable behaviour and clear logs.
- When the design doc leaves a decision open, do not decide silently. Ask with concrete options ("A or B?") and a recommendation, then record the answer in the decisions table.
- He writes in Turkish, German and English, often mixed. Reply in the language of his message.
