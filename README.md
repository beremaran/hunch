# Hunch

A local AI with a human-like memory. It remembers, forgets, learns from experience, changes its mind, and follows up on open topics. One shared personality talks to several users over Telegram. Everything runs on one Windows PC with an open model (Qwen3.5-9B, 4-bit); nothing leaves the machine.

"Consciousness" in the project name is a metaphor. The goal is a measurable, testable functional imitation of human memory, not a claim about awareness.

**New here? Start with [`docs/STORY.md`](docs/STORY.md)**: why Hunch exists and how it works, in plain language and without the detail.

## Status

Phases 0–4 are done and measured. Phase 5 (mood, multi-user privacy, forgetting) is built, unit-tested (1312 tests), committed (`ae2b2d9`), and its phase-end sweep has run: golden, eval, bench and probes, see [`reports/phase5/REPORT.md`](reports/phase5/REPORT.md) §10. Phase 5 is done (22 Oct). Two items carry over to Phase 6: the privacy question is never asked on calm turns and has no regression test, and the "I don't have any information about Anna" phrasing (REPORT §7.5) is not investigated. Phase 6 (Telegram and open loops) is next.

| Phase | What | Report |
| --- | --- | --- |
| 0 | Setup, 4-bit model, first eval set | `eval/results/phase0-baseline/REPORT.md` |
| 1 | Core values loader (read-only, fail-closed) | `eval/results/phase1/` |
| 2 | Memory store, activation engine, cue extraction, recall | [`reports/phase2/REPORT.md`](reports/phase2/REPORT.md) |
| 3 | Turn pipeline as a local CLI chat | [`reports/phase3/REPORT.md`](reports/phase3/REPORT.md) |
| 4 | Hunch and graded reflection | [`reports/phase4/REPORT.md`](reports/phase4/REPORT.md) |
| 5 | Mood, multi-user privacy, forgetting | [`reports/phase5/PROPOSAL.md`](reports/phase5/PROPOSAL.md) (done) |
| 6+ | Telegram bot and open loops, nightly consolidation, steering, log viewer, small chat app | roadmap at the end of `docs/design.md` |

Latest measured state (end of Phase 4): 699 unit tests, 14/14 GPU golden tests, eval 100% clean with 0 invented memories and 0 "I have no memory" replies, 0 of 51 replies over the 10 s latency budget (median about 6 s).

## Documentation

| File | What it is | Language |
| --- | --- | --- |
| [`docs/STORY.md`](docs/STORY.md) | Purpose and story of the project, how it works, what went wrong and what was learned | English |
| [`docs/design.md`](docs/design.md) | The full design: architecture, formulas, the decisions table (who decided what), risks, roadmap. Single source of truth | Turkish |
| [`CLAUDE.md`](CLAUDE.md) | Working rules, the 11 invariants, conventions, test levels, target layout | English |
| [`docs/claude-code-prompts.md`](docs/claude-code-prompts.md) | Step-by-step phase prompts used to build the project with Claude Code | English |
| `reports/phaseN/REPORT.md` | Per-phase results: what was built, what was measured, what is still open | English |
| `eval/results/` | Eval summaries and diffs between phases | English |
| [`core/values.yaml`](core/values.yaml) | The five core values (read-only at runtime) | English |

## Layout

```
src/hunch/   llm, values, memory, recall, drive, reflection, pipeline, observability, ...
core/        values.yaml, read-only at runtime
tests/       unit tests; tests/golden/ needs the GPU and the model
eval/        regression suite and blind probe sets
reports/     per-phase reports
docs/        design, story, prompts
```

`mood/` (global mood, relationships) and `privacy/` (privacy profile, sensitive categories) are filled since Phase 5; `loops/`, `consolidation/` and `channels/` are still empty packages, filled in Phases 6–7. Admin commands (find, forget, archive): `python -m hunch.admin`.

## Setup (Windows)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cu130
.venv\Scripts\python.exe -m pip install -e ".[llm,dev]"
copy .env.example .env
```

Needs a CUDA GPU (developed on an RTX 4070 Ti Super, 16 GB) for the model. Unit tests run on the CPU.

## Running and testing

- Local chat: `.venv\Scripts\python.exe -m hunch.cli --user <name> [--verbose]`
- Unit tests (about 25 s, CPU only): `.venv\Scripts\python.exe -m pytest -q`
- Lint: `.venv\Scripts\ruff.exe check .`
- Golden tests (GPU and model): `.venv\Scripts\python.exe -m pytest -m golden`
- Eval (English, 3 samples per prompt): `.venv\Scripts\python.exe -m eval.run_eval --tag <name> --pipeline`; compare two runs with `python -m eval.compare <old> <new>`
- Model benchmark: `.venv\Scripts\python.exe scripts\bench_llm.py --tag <name>`

Test levels (L1 unit, L2 per area, L3 small GPU regression set, L4 full sweep at phase end) are described in `CLAUDE.md`.

## Core values

`core/values.yaml` is loaded read-only at startup; if it is missing or malformed the system refuses to start. No code in `src/` can write to `core/` or `.env` (enforced by `tests/test_no_core_writes.py`). The AI can only file proposals in `data/amendments/pending/`. Signing is deferred to a later phase.
