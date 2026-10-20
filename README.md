# Hunch

İnsan benzeri hafızaya sahip yerel bir yapay zeka: hatırlar, unutur, tecrübeden ders çıkarır, fikir değiştirir ve açık kalan konuları kendiliğinden takip eder. Tek bir ortak kişilik, Telegram üzerinden birden çok kullanıcıyla konuşur.

- Tasarım: [`docs/design.md`](docs/design.md)
- Claude Code için adım adım prompt'lar: [`docs/claude-code-prompts.md`](docs/claude-code-prompts.md)
- Claude Code proje talimatları: [`CLAUDE.md`](CLAUDE.md)
- Çekirdek değerler (taslak, imzasız): [`core/values.yaml`](core/values.yaml)

Durum: Faz 0 (kurulum ve model kontrolü).

## Setup (Windows)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cu130
.venv\Scripts\python.exe -m pip install -e ".[llm,dev]"
copy .env.example .env
```

- Tests and lint: `.venv\Scripts\python.exe -m pytest` and `.venv\Scripts\ruff.exe check .`
- Model benchmark: `.venv\Scripts\python.exe scripts\bench_llm.py --tag <name>`
- Eval set (English, 3 samples per prompt): `.venv\Scripts\python.exe -m eval.run_eval --tag <name>`; results in `eval/results/<name>/`; diff two runs with `python -m eval.compare <old> <new>`
- Golden tests (GPU + model): `.venv\Scripts\python.exe -m pytest -m golden`

## Core values

`core/values.yaml` is loaded read-only at startup; if it is missing or malformed the system refuses to start. No code in `src/` can write to `core/` or `.env`. The AI can only file proposals in `data/amendments/pending/`. Signing is deferred to a later phase.
