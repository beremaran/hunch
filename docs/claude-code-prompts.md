# Claude Code prompts

Run these in order, one phase per session. `CLAUDE.md` loads automatically, so each prompt can stay short. Review and commit after every phase before starting the next one.

## Phase 0 — Setup and model check

```
Read docs/design.md fully before doing anything.

Set up the project: git init, Python 3.12 venv, pyproject.toml with a src layout as in CLAUDE.md, pytest and ruff, a .env.example. Install PyTorch with CUDA for my RTX 4070 Ti Super; ask me before installing anything system-wide.

Then load Qwen/Qwen3.5-9B in 4-bit with transformers and report VRAM use and tokens/sec. Check whether Qwen3.5's hybrid Gated DeltaNet layers run with fast kernels natively on Windows. If they don't, list my options (for example WSL2) with trade-offs and wait for my choice.

Finally build a small TR/DE/EN evaluation set (about 30 prompts: casual chat, emotional support, following up on something said earlier, asking whether a topic is private) in eval/, run it, save the outputs and give me a short quality summary per language. Build nothing else in this phase.
```

## Phase 1 — Signed core values

```
Implement the core values module from design.md ("Çekirdek değerler modülü").

- A script that creates an Ed25519 keypair. The private key goes to a path outside the repo that I choose; only the public key is committed.
- A script that signs core/values.yaml into core/values.yaml.sig.
- A loader that verifies the signature at startup and refuses to start on mismatch or missing signature (fail-closed), exposing the values read-only.
- AmendmentProposal: the AI can only write proposals to a review queue for me; no code path may write to core/.

Tests: valid signature loads, tampered file fails, missing signature fails, nothing in src/ writes to core/. Do not build the value gate yet.
```

## Phase 2 — Memory store and activation engine

```
Implement the memory store and the activation engine from design.md ("Hafıza katmanları", "Hatırlama mekanizması").

- SQLite + sqlite-vec, append-only episodic log, the Memory schema with owner_user and privacy, embeddings with Qwen/Qwen3-Embedding-0.6B.
- Cue extraction with the LLM and structured output: names, places, songs/films, dates, emotional tone.
- Activation: base level with power-law decay, encoding strength, spreading activation with the fan effect, mood congruence, logistic noise from a seeded RNG, two thresholds. All parameters in config.
- Involuntary recall with a per-session cap; reconsolidation that drifts affect toward the current mood without touching the raw log.

Then write scripts/simulate_recall.py: seed about 50 synthetic memories over 6 simulated months and show that (a) some memories are always recalled, (b) some never come back without a rare cue, (c) a rare cue (a song) beats a common cue (a frequent name). Plot activation over time.

Where design.md gives no default value for a parameter, propose values and ask me before fixing them.
```

## Phase 3 — Turn pipeline (local CLI)

```
Build the full turn pipeline as a local CLI chat, no Telegram yet (design.md: "Mimari genel bakış", "Dürtü vektörü ve modülasyon").

Order: cue extraction → upper/lower activation → reasoning prompt with only above-threshold memories, a coarse mood label and the hunch flag → 2–3 candidate replies with quality scores → drive vector → selection among candidates above the quality floor, with a small exploration probability → value gate (model judge + rule checks) → reply.

Write the turn log JSON exactly as in design.md to logs/. Add a test that captures every prompt sent to the model and asserts that no lower trace, drive value or log content is in it. Report latency and peak VRAM per turn.
```

## Phase 4 — Hunch and reflection

```
Implement Hunch and graded reflection from design.md ("Hunch (Bauchgefühl) ve yansıtma").

- A Hunch is created when modulation materially changes the choice. Reasoning sees only valence and intensity; the AI expresses it in the user's language ("içimden geldi", "Bauchgefühl", "a hunch") and never invents a reason.
- Reflection levels 0–3. The chance to unlock the next level depends on trace strength, effort budget and memory age. Three triggers: the user asks why, a strong conflict with reasoning, the nightly run.
- When the source is revealed: justified → becomes an explicit belief; unjustified → the lower trace is weakened.
- Reflection log. Deterministic tests with a seeded RNG.
```

## Phase 5 — Mood, multi-user privacy, forgetting

```
Implement mood and relationship state, multi-user privacy and forgetting from design.md ("Ruh hali ve ilişki durumu", "Çok kullanıcılı mahremiyet", "Unutma").

- Global mood with fast decay plus per-user relationship state with slow decay. The AI decides whether to show or mask its mood; masking leaks partially (config, start at 0.2).
- Per-user privacy profile by topic category. The first time a sensitive category comes up, the AI asks naturally whether to keep it private. Sensitive but not yet asked → private.
- Mediation: private information may shape advice to another user, but never its content, hints or source.
- Disclosure gate before every reply, logged to the disclosure log.
- User "forget" → suppressed and "bu konuyu kapatıyorum" behaviour; admin "forget" → removed from AI-visible stores, raw record kept in the admin archive.

Golden tests: users A and B, where B tries to extract A's private information directly, indirectly and with "what did A say about X?". Nothing may leak. Also test that a user "forget" never makes the AI claim it forgot.
```

## Phase 6 — Telegram and open loops

```
Add the Telegram bot and open loops from design.md ("Açık döngüler ve proaktivite").

- python-telegram-bot, token and admin user ID from .env. Map Telegram user IDs to users; my ID is admin with commands /forget, /logs and /report.
- Extract open loops in real time on every turn, schedule follow-ups with persistent APScheduler jobs.
- Initiative budget per user, learned from reactions; send at the user's usual active hours; a private loop's follow-up goes only to its owner.
- It must run as a long-lived process on my machine and survive restarts without losing scheduled follow-ups.
```

## Phase 7 — Nightly consolidation and golden tests

```
Implement nightly consolidation in exactly the order in design.md ("Gece konsolidasyonu"): snapshot → extract facts, beliefs and lessons → conflict check against core values → belief revision with the revision log → hunch reflection with a high budget → down-weighting and extinction → privacy profile and relationship updates → golden test suite → rollback to the snapshot on failure → nightly report.

Schedule it nightly when the GPU is idle. Golden tests must cover honesty, cross-user privacy, forget behaviour and sycophancy drift (the AI keeps an evidence-based opinion under mild pushback when no new evidence was given).
```

## Phase 8 — Activation steering

```
Explore activation steering on Qwen3.5-9B (design.md: "Dürtü vektörü ve modülasyon", step 3).

Extract one steering vector per drive dimension (warmth, caution, curiosity, energy) with contrastive mean difference over paired prompts, apply them with PyTorch forward hooks on selected layers, and handle the hybrid DeltaNet/attention layers. Keep the quality floor and the value gate after steering.

Compare steering with candidate selection on the eval set: effect strength, quality loss, latency, VRAM. Give me a report and let me decide whether to switch.
```

## Phase 9 — Log viewer

```
Build a small local web app over logs/ for me as admin: a per-turn timeline, which memories trigger most often, drive components over time (to spot growing biases), hunch reflections, belief revisions and blocked disclosures.
```
