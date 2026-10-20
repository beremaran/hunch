# Hunch — AI Memory Consciousness System

A local AI with a human-like memory: it remembers, forgets, learns from experience, changes its mind, takes initiative and follows up on open topics. One shared personality talks to several users over Telegram.

**Source of truth:** `docs/design.md` (Turkish). Read it before any design-relevant change. The decisions table in that file lists what Berk (owner/admin) decided and what is only a default proposed by Claude.

**Status:** design finished, no code yet. Work follows the MVP roadmap at the end of `docs/design.md`. Step-by-step prompts are in `docs/claude-code-prompts.md`.

## Environment

- Windows PC, NVIDIA RTX 4070 Ti Super (16 GB VRAM), 32 GB RAM. Project root: `C:\hunch`.
- Python 3.12, PyTorch + CUDA, Hugging Face transformers.
- Main model: `Qwen/Qwen3.5-9B`, 4-bit. Hybrid architecture (Gated DeltaNet + attention): check kernel support on Windows; if something only works well under WSL2, say so and let Berk decide.
- Embeddings: `Qwen/Qwen3-Embedding-0.6B` (CPU is fine if VRAM is tight).
- Storage: SQLite + sqlite-vec. Scheduler: APScheduler. Channel: Telegram bot.
- Before installing anything system-wide (CUDA toolkit, WSL, drivers), ask first.

## Invariants (never break these)

1. **Raw episodic log is append-only.** Never update or delete raw records. A user "forget" only marks a memory `suppressed`. An admin "forget" removes the memory and its derived beliefs and lower traces from AI-visible stores; the raw record stays in an admin-only archive.
2. **The lower layer never reaches the prompt as content.** Lower traces, the drive vector and modulation logs must never appear in any model prompt. The only things allowed through: the hunch flag (valence, intensity) and a coarse mood label.
3. **No write path to core values.** `core/values.yaml` is loaded read-only and verified with an Ed25519 signature at startup; on mismatch the system refuses to start (fail-closed). The AI can only create an `AmendmentProposal` for Berk to review. The private signing key never goes into the repo.
4. **Order of the turn:** reasoning → candidates → modulation → value gate → reply. The value gate is always last.
5. **Quality floor:** modulation only chooses among candidates above the quality threshold.
6. **Cross-user privacy:** a user's `private` memories must never appear in, or be hinted at by, a reply to another user. The disclosure check is rule-based plus a model judge, never the model judge alone.
7. **Admin sees everything, the AI sees none of its own modulation.** Every internal decision is logged for the admin; logs are never fed back to the AI.
8. **Multi-user from day one:** every memory carries `owner_user` and `privacy`.
9. **Do not do everything on your own, delegate to sub agents when needed. Choose models based on the task complexity.

## Conventions

- Code, identifiers, comments and commit messages in English. `docs/design.md` stays in Turkish; when a decision changes, update its decisions table.
- Type hints everywhere, `pytest` for tests, `ruff` for lint and format.
- All tunable parameters (activation d, α, μ, S, noise, thresholds τ_upper/τ_lower, decay rates, mood leak, initiative budget, candidate count, quality floor) live in one config file, not hardcoded.
- Randomness (recall noise, exploration, reflection) goes through a seedable RNG so tests are deterministic.
- Keep GPU work behind one `llm` module so the model can be swapped (see the upgrade path in the design doc).
- Secrets (Telegram token, admin ID, key paths) in `.env`, never committed.


## Target layout

```
src/hunch/
  config.py
  llm/            # model loading, generation, steering hooks
  values/         # signed values loader, AmendmentProposal, value gate
  memory/         # episodic store, Memory schema, embeddings
  recall/         # cue extraction, activation engine, involuntary recall
  drive/          # drive vector, modulation, Hunch
  reflection/     # graded hunch reflection
  mood/           # global mood, per-user relationship state
  privacy/        # privacy profiles, disclosure gate
  loops/          # open loops, initiative budget, scheduler
  consolidation/  # nightly job
  channels/       # telegram
  observability/  # turn, reflection, revision, disclosure logs; nightly report
core/             # values.yaml + values.yaml.sig (read-only at runtime)
tests/  tests/golden/
scripts/  eval/
data/  logs/      # gitignored
```

## Working with Berk

- Berk is a test architect: he values tests, measurable behaviour and clear logs.
- When the design doc leaves a decision open, do not decide silently. Ask with concrete options ("A or B?") and a recommendation, then record the answer in the decisions table.
- He writes in Turkish, German and English, often mixed. Reply in the language of his message.
