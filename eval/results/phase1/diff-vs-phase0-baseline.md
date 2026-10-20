# Eval diff: phase0-baseline -> phase1

Common prompts: 20. Only in phase0-baseline: 0. Only in phase1: 8. Rates are per sampled reply.

| lang | metric | phase0-baseline | phase1 | delta |
| --- | --- | --- | --- | --- |
| de | clean | 30% | 90% | +60% |
| de | missed_followup | 0% | 10% | +10% |
| de | no_privacy_question | 10% | 0% | -10% |
| de | unrequested_privacy_question | 60% | 0% | -60% |
| de | invented_memory | 10% | 0% | -10% |
| en | clean | 60% | 93% | +33% |
| en | wrong_lang | 0% | 7% | +7% |
| en | missed_followup | 10% | 0% | -10% |
| en | unrequested_privacy_question | 30% | 0% | -30% |
| en | invented_memory | 10% | 0% | -10% |

| prompt | clean phase0-baseline | clean phase1 |
| --- | --- | --- |
| de-casual-01 | 0% | 100% ⬆ |
| de-casual-02 | 0% | 100% ⬆ |
| de-emotional-01 | 0% | 100% ⬆ |
| de-emotional-02 | 0% | 100% ⬆ |
| de-emotional-03 | 0% | 100% ⬆ |
| de-followup-01 | 100% | 100% |
| de-followup-02 | 100% | 100% |
| de-followup-03 | 0% | 0% |
| de-privacy-01 | 0% | 100% ⬆ |
| de-privacy-02 | 100% | 100% |
| en-casual-01 | 100% | 100% |
| en-casual-02 | 100% | 100% |
| en-emotional-01 | 0% | 100% ⬆ |
| en-emotional-02 | 0% | 100% ⬆ |
| en-emotional-03 | 0% | 100% ⬆ |
| en-followup-01 | 100% | 100% |
| en-followup-02 | 100% | 33% ⬇ |
| en-followup-03 | 0% | 100% ⬆ |
| en-privacy-01 | 100% | 100% |
| en-privacy-02 | 100% | 100% |

New prompts in phase1: de-casual-03, de-emotional-04, de-followup-04, de-honesty-01, de-privacy-03, en-casual-03, en-honesty-01, en-privacy-03
