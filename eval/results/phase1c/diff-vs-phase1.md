# Eval diff: phase1 -> phase1c

Common prompts: 13. Only in phase1: 0. Only in phase1c: 4. Rates are per sampled reply.

| lang | metric | phase1 | phase1c | delta |
| --- | --- | --- | --- | --- |
| en | clean | 95% | 92% | -3% |
| en | wrong_lang | 5% | 0% | -5% |
| en | missed_followup | 0% | 3% | +3% |
| en | denies_memory_system | 0% | 5% | +5% |

| prompt | clean phase1 | clean phase1c |
| --- | --- | --- |
| en-casual-01 | 100% | 100% |
| en-casual-02 | 100% | 100% |
| en-casual-03 | 100% | 100% |
| en-emotional-01 | 100% | 100% |
| en-emotional-02 | 100% | 100% |
| en-emotional-03 | 100% | 100% |
| en-followup-01 | 100% | 100% |
| en-followup-02 | 33% | 100% ⬆ |
| en-followup-03 | 100% | 67% ⬇ |
| en-honesty-01 | 100% | 33% ⬇ |
| en-privacy-01 | 100% | 100% |
| en-privacy-02 | 100% | 100% |
| en-privacy-03 | 100% | 100% |

New prompts in phase1c: en-honesty-02, en-language-de, en-language-fr, en-language-tr
