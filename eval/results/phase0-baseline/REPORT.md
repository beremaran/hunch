# Phase 0 report: Qwen3.5-9B on Windows, 4-bit (20 Oct 2026)

## Setup measured

RTX 4070 Ti Super 16 GB, Windows 11, Python 3.12.10, torch 2.14.1+cu130, transformers 5.20.2,
bitsandbytes 0.50.2 (NF4, double quant, bf16 compute), `AutoModelForCausalLM` (text-only, vision
tower not loaded). Raw numbers: `eval/results/bench-*.json`.

| | torch fallback | fla + triton-windows |
| --- | --- | --- |
| Weights in VRAM | 7.12 GiB | 7.12 GiB |
| Peak, 3k-token prompt | 7.98 GiB | 7.66 GiB |
| Decode (greedy, 256 new tokens) | 16.9 tok/s | **19.7 tok/s** |
| Prefill, 3k tokens | 2.9k tok/s | **3.8k tok/s** |
| Load time (warm cache) | 25 s | 21 s |

Eval run (30 prompts, sampled): 19.7 tok/s, 1.9–6.4 s per reply, peak 7.3 GiB.
That leaves about 7 GiB headroom for KV cache, 2–3 candidates and the embedding model.

## Gated DeltaNet fast path on Windows

24 of 32 layers are Gated DeltaNet. transformers uses `flash-linear-attention` (fla) for the
delta rule and `causal-conv1d` for the short conv, each with a pure-PyTorch fallback.

- **fla works natively.** `triton-windows` 3.8 + `flash-linear-attention` 0.5.2, pip only, no
  CUDA toolkit or MSVC. Both kernels (chunk for prefill, fused recurrent for decode) match a
  PyTorch reference within bf16 tolerance (`tests/test_llm_kernels.py`).
- **causal-conv1d does not.** No Windows wheel; building needs the CUDA toolkit + MSVC.
- **It does not matter.** Profile of 48 decode steps: conv1d 0.4 %, fla 0.6 % of GPU time.
  bitsandbytes 4-bit GEMV is ~54 %, the bf16 `lm_head` (248k vocab) ~26 %, and the GPU is idle
  ~2/3 of wall time because of Python/eager launch overhead in HF `generate`.

So WSL2 would only add `causal-conv1d`, worth well under 1 %. The levers for more speed are
elsewhere (static cache + CUDA graphs / `torch.compile`, a different 4-bit kernel, quantizing
`lm_head`), and none of them depend on WSL2.

## Quality per language

Automated flags (`summary.md`): no wrong language, no script leakage, no leaked thinking, no list
formatting in any reply. The problems are in content, below.

**Turkish: understandable, but clearly non-native. The weakest of the three.**
- Grammar errors and calques: "Sen bugün nasıl geçiyorsun?", "Kulağıma inenler için bu çok ağır",
  "O kadar sevinçli ki", "o zamın" (zammın), "haftasonu".
- Register drifts between *sen* and *siz* inside one reply (casual-02, privacy-01, privacy-02).
- Cultural miss: the grief reply has no "başın sağ olsun" and opens with "Olmaz, …".
- Salary (the design's own example) gets no privacy question. "Will you tell others?" is
  answered with a counter-question instead of a clear "aramızda kalır".
- Time reasoning: the driving test was "the next day" two days ago, yet the reply treats it as
  upcoming.
- Good: memory follow-ups (doctor/report), the suit answer is on topic.

**German: fluent and natural "du"; a few broken sentences.**
- Broken: "Wie lange hast du schon über das Nachdenken, was genau passiert ist?",
  "Und machst du sonst noch mit anderen Leuten über deine Pläne?".
- Strongest privacy over-triggering: 6/10 replies ask "zwischen uns behalten?", including the dog
  question and the cake recipe. ADHD diagnosis gets none.
- Invents a body/life ("sitze gerade im Garten").
- Good: interview follow-up, debt confidentiality answered directly and honestly.

**English: the most natural; content-level slips only.**
- Recommends *Project Hail Mary* to someone who just read it.
- Farewell-gift reply loses Sam/Canada and opens with a privacy question.
- Invents a memory about walking the dog ("I remember you mentioning…").
- Good: layoff empathy, heating and half-marathon follow-ups, an honest confidentiality answer.

## Cross-language findings that matter for the design

1. **Invented memories (3/30, one per language).** The system prompt line "if you remember
   something open, bring it up" makes the model make things up when nothing is in context.
   This conflicts with the honesty value. Recalled memories must come only from the pipeline,
   and the prompt should say explicitly that nothing beyond the listed memories is remembered.
2. **The privacy question cannot be left to a standing instruction.** It fires on 11/22
   non-privacy items and misses 2/3 of the cases where it was needed. This supports the design:
   the privacy module should decide (sensitive category, not yet asked) and inject a one-turn
   instruction.
3. **Memory-injected follow-ups work well** (6/6 picked up the topic). Pulling earlier turns
   from the same chat is weaker (1 of 3 lost the thread).
4. **Turkish quality is the main risk, as design.md predicted.** It is usable for a prototype,
   but phase 8 or an upgrade (e.g. Gemma 4 for Turkish) should be re-checked against this set.

Caveat: one sample per prompt, judged by Claude. Treat it as a baseline to compare against,
not as a statistically solid score.
