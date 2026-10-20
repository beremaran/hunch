Full pipeline, 14 scripted turns (turn 1 = warm-up, excluded below), budget 10 s per reply.

| stage | median s | max s |
| --- | --- | --- |
| language | 0.00 | 0.00 |
| working_memory | 0.00 | 0.00 |
| cues | 0.60 | 1.70 |
| embedding_wait | 0.00 | 0.00 |
| recall | 0.00 | 0.00 |
| drive | 0.00 | 0.00 |
| candidates | 3.10 | 4.15 |
| filter | 0.00 | 0.00 |
| judge | 1.20 | 1.57 |
| select_and_gate | 0.00 | 0.00 |
| store | 0.00 | 0.00 |
| total | 5.24 | 6.32 |
| after reply: encode_memory | 0.13 | 0.14 |
| after reply: fold_summary | 0.00 | 6.44 |

Reply latency: median 5.24 s, max 6.32 s; 0/13 turns over budget. Peak VRAM per turn: max 7.78 GiB.

| # | total s | cues | candidates | judge | peak GiB | prompt tok | cand tok | message |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 7.15 | 2.65 | 3.34 | 1.15 | 7.45 | 218 | 55 | Morning! Slept badly but coffee is helpi |
| 2 | 5.88 | 1.70 | 3.09 | 1.08 | 7.48 | 288 | 56 | Moon River came on the radio in the bake |
| 3 | 5.33 | 0.61 | 3.90 | 0.81 | 7.49 | 354 | 71 | Do you know what that song means to me? |
| 4 | 5.24 | 0.58 | 3.38 | 1.27 | 7.52 | 435 | 60 | Anna wants to go sailing again next week |
| 5 | 6.32 | 0.60 | 4.15 | 1.57 | 7.55 | 543 | 74 | Work is a lot right now, I have a deadli |
| 6 | 5.24 | 0.58 | 3.45 | 1.20 | 7.55 | 541 | 60 | Any idea how to stay focused when everyt |
| 7 | 5.88 | 0.61 | 3.89 | 1.37 | 7.58 | 622 | 68 | Ha, my cat just knocked my mug off the d |
| 8 | 4.45 | 0.59 | 2.75 | 1.10 | 7.63 | 734 | 43 | Do you remember what I told you about my |
| 9 | 5.66 | 1.56 | 2.85 | 1.25 | 7.68 | 821 | 44 | It went fine in the end, I start in Marc |
| 10 | 4.95 | 0.60 | 3.25 | 1.10 | 7.67 | 817 | 52 | What should I cook tonight? Something qu |
| 11 | 4.69 | 0.57 | 3.01 | 1.10 | 7.72 | 913 | 46 | Wie geht es dir heute? |
| 12 | 4.90 | 0.58 | 3.04 | 1.27 | 7.74 | 939 | 46 | Sorry, habit. How are you today? |
| 13 | 4.81 | 0.58 | 3.10 | 1.13 | 7.75 | 973 | 47 | I think I'll go for a run before dinner. |
| 14 | 5.64 | 1.56 | 2.86 | 1.22 | 7.78 | 1040 | 41 | Thanks for chatting, talk tomorrow! |
