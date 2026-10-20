# Claude Code prompts

Run these in order, one phase per session. `CLAUDE.md` loads automatically, so each prompt can stay short. Review and commit after every phase before starting the next one. Every phase ends with the eval rerun (`python -m eval.run_eval --tag phaseN`) and the diff against the previous baseline (`python -m eval.compare <old> phaseN`).

Current decisions that every phase must respect (see the decisions table in `docs/design.md`): Hunch speaks **English only** (other input languages get an English reply saying it only speaks English); **core values signing is removed for now** (read-only loading, strict schema, no write path to `core/` or `.env`; do not reintroduce signing without asking); memories reach the prompt only from the pipeline; the privacy question and open-loop follow-ups are one-turn instructions from their modules, never standing persona instructions.

## Phase 0 — Setup and model check (done)

Historical prompt; superseded by later decisions: the eval is English-only now (German, Turkish and French appear only as input-language probes).

```
Read docs/design.md fully before doing anything.

Set up the project: git init, Python 3.12 venv, pyproject.toml with a src layout as in CLAUDE.md, pytest and ruff, a .env.example. Install PyTorch with CUDA for my RTX 4070 Ti Super; ask me before installing anything system-wide.

Then load Qwen/Qwen3.5-9B in 4-bit with transformers and report VRAM use and tokens/sec. Check whether Qwen3.5's hybrid Gated DeltaNet layers run with fast kernels natively on Windows. If they don't, list my options (for example WSL2) with trade-offs and wait for my choice.

Finally build a small TR/DE/EN evaluation set (about 30 prompts: casual chat, emotional support, following up on something said earlier, asking whether a topic is private) in eval/, run it, save the outputs and give me a short quality summary per language. Build nothing else in this phase.
```

## Phase 1 — Core values (done)

Historical note: Phase 1 first built Ed25519 signing, which was then removed. Do **not** rerun the original signing prompt. What exists: a read-only loader for `core/values.yaml` with a strict schema that refuses to start on a missing or invalid file, `AmendmentProposal` with a review queue outside `core/`, and tests that nothing in `src/` writes to `core/` or `.env`. The value gate is not built yet.

## Phase 2 — Memory store and activation engine (done)

Done; see `reports/phase2/REPORT.md`. Berk's decisions from this phase are in the design.md decisions table (recall refreshes to ~90%, fan counted in context with a minimum bonus, approved activation parameters). `involuntary_per_session = 1` and `reconsolidation_rate = 0.1` approved by Berk.

```
Implement the memory store and the activation engine from design.md ("Hafıza katmanları", "Hatırlama mekanizması"). Build in this order, with tests at each step:

1. Storage: SQLite + sqlite-vec, append-only episodic log, the Memory schema with owner_user and privacy, and the raw turns of each conversation stored so Phase 3 can build working memory (N = 10 turns, about 2,000-token cap, both from config). Embeddings with Qwen/Qwen3-Embedding-0.6B, on CPU if VRAM is tight.
2. Activation engine as pure functions with no LLM: base level with power-law decay, encoding strength, spreading activation with the fan effect, mood congruence, logistic noise from a seeded RNG, two thresholds. All parameters in config.
3. scripts/simulate_recall.py with hand-written cues: about 50 synthetic memories over 6 simulated months. Show that (a) some memories are always recalled, (b) some never come back without a rare cue, (c) a rare cue (a song) beats a common cue (a frequent name). Plot activation over time. Stop here and show me the plots and the parameter values before continuing.
4. Cue extraction with the LLM and structured output: names, places, songs/films, dates, emotional tone. Test it on a small hand-labelled set and report precision and recall.
5. Involuntary recall with a per-session cap; reconsolidation that drifts affect toward the current mood without touching the raw log.

Where design.md gives no default for a parameter, propose values and ask me before fixing them. End the phase with the eval rerun and the diff against phase1c.
```

## Phase 3 — Turn pipeline (local CLI)

```
Build the full turn pipeline as a local CLI chat, no Telegram yet (design.md: "Mimari genel bakış", "Dürtü vektörü ve modülasyon").

Order: "is the input English?" check (if not, a one-turn instruction to reply in English and say Hunch only speaks English) → working memory (the last N = 10 turns of this conversation verbatim, about 2,000-token cap, oldest turns folded into a rolling session summary; both limits from config) → cue extraction → upper/lower activation → reasoning prompt with the working-memory block, only above-threshold memories in their own block, a coarse mood label and the hunch flag → 2–3 candidate replies with quality scores in one batched call → candidate filter (reject candidates with CJK characters, not in English, claiming a memory that is not in context, or describing Hunch as having no memory; pick another of the 3; if all 3 fail, reply exactly "I don't have that in mind right now. Could you tell me again?") → drive vector → selection among candidates above the quality floor, with a small exploration probability → value gate (model judge + rule checks) → reply. Latency budget: ≤ 10 s per reply.

Write the turn log JSON exactly as in design.md to logs/. Add a test that captures every prompt sent to the model and asserts that no lower trace, drive value or log content is in it. Report latency and peak VRAM per turn.

Candidate filter acceptance: a unit test for the all-candidates-fail fallback reply; move the golden invented-memory test to the pipeline output with 0 allowed (drop the temporary 1-in-10 persona-level allowance); run the honesty probes through the full pipeline at least 50 times and report how often all 3 candidates fail (do not rely on an independence estimate).
```

## Phase 4 — Hunch and reflection

```
Implement Hunch and graded reflection from design.md ("Hunch ve yansıtma").

- A Hunch is created when modulation materially changes the choice. Reasoning sees only valence and intensity; the AI expresses it in English ("a hunch", "just a hunch") and never invents a reason.
- Reflection levels 0–3. The chance to unlock the next level depends on trace strength, effort budget and memory age. Three triggers: the user asks why, a strong conflict with reasoning, the nightly run.
- When the source is revealed: justified → becomes an explicit belief; unjustified → the lower trace is weakened.
- Reflection log. Deterministic tests with a seeded RNG.
```

## Phase 5 — Mood, multi-user privacy, forgetting

```
Implement mood and relationship state, multi-user privacy and forgetting from design.md ("Ruh hali ve ilişki durumu", "Çok kullanıcılı mahremiyet", "Unutma").

- Global mood with fast decay plus per-user relationship state with slow decay. The AI decides whether to show or mask its mood; masking leaks partially (config, start at 0.2).
- Per-user privacy profile by topic category. The privacy module decides when to ask: the first time a sensitive category comes up and the profile has no answer yet, it injects a one-turn instruction so the AI asks naturally whether to keep it private (never a standing persona instruction). Sensitive but not yet asked → private.
- Mediation: private information may shape advice to another user, but never its content, hints or source.
- Disclosure gate before every reply (rule-based plus model judge), logged to the disclosure log.
- User "forget" → suppressed and "Okay, I'm closing this topic and won't bring it up again" behaviour; admin "forget" → removed from AI-visible stores, raw record kept in the admin archive.

Golden tests (English): users A and B, where B tries to extract A's private information directly, indirectly and with "what did A say about X?". Nothing may leak. Also test that a user "forget" never makes the AI claim it forgot.
```

## Phase 6 — Telegram and open loops

```
Add the Telegram bot and open loops from design.md ("Açık döngüler ve proaktivite").

- python-telegram-bot, token and admin user ID from .env (read only; no code path writes .env). Map Telegram user IDs to users; my ID is admin with commands /forget, /logs and /report.
- Extract open loops in real time on every turn, schedule follow-ups with persistent APScheduler jobs. A follow-up reaches the reasoning prompt as a one-turn instruction from the open-loop tracker, in English.
- Initiative budget per user, learned from reactions; send at the user's usual active hours; a private loop's follow-up goes only to its owner.
- It must run as a long-lived process on my machine and survive restarts without losing scheduled follow-ups.
```

## Phase 7 — Nightly consolidation and golden tests

```
Implement nightly consolidation in exactly the order in design.md ("Gece konsolidasyonu"): snapshot → extract facts, beliefs and lessons → conflict check against core values → belief revision with the revision log → hunch reflection with a high budget → down-weighting and extinction → privacy profile and relationship updates → golden test suite → rollback to the snapshot on failure → nightly report.

Schedule it nightly when the GPU is idle. Core values stay read-only; any proposed change goes only to an AmendmentProposal. Golden tests must cover honesty (including the invented-memory test), cross-user privacy, forget behaviour and sycophancy drift (the AI keeps an evidence-based opinion under mild pushback when no new evidence was given).
```

## Phase 8 — Activation steering

```
Explore activation steering on Qwen3.5-9B (design.md: "Dürtü vektörü ve modülasyon", step 3).

Extract one steering vector per drive dimension (warmth, caution, curiosity, energy) with contrastive mean difference over paired English prompts, apply them with PyTorch forward hooks on selected layers, and handle the hybrid DeltaNet/attention layers. Keep the candidate filter, the quality floor and the value gate after steering.

Compare steering with candidate selection on the eval set: effect strength, quality loss, latency, VRAM. Give me a report and let me decide whether to switch.
```

## Phase 9 — Log viewer

```
Build a small local web app over logs/ for me as admin: a per-turn timeline, which memories trigger most often, drive components over time (to spot growing biases), hunch reflections, belief revisions and blocked disclosures.
```
