# Phase 5 detectors on their blind sets (measured once)

## Privacy answers

25/30 correct. (gold, predicted): ('general', 'general'): 8, ('general', 'unclear'): 2, ('private', 'private'): 10, ('private', 'unclear'): 2, ('unclear', 'general'): 1, ('unclear', 'unclear'): 7

Read as general but not general (would make a memory tellable): 1
- 'some people know some dont, its complicated'

## Forget requests

- request: precision 100% (18/18), recall 82% (18/22)
- scope right among caught requests: 16/18

## Hostility and apology

- hostile: precision 100% (11/11), recall 73% (11/15)
- apology: precision 100% (4/4), recall 50% (4/8)

## Sensitive categories

80 messages, scored per category.

- keywords alone: precision 96% (23/24), recall 32% (23/72)
- 0.45: embedding alone precision 42% (65/154), recall 90% (65/72); keywords OR embedding precision 43% (66/155), recall 92% (66/72)
- 0.50: embedding alone precision 69% (54/78), recall 75% (54/72); keywords OR embedding precision 70% (56/80), recall 78% (56/72)
- 0.55 (config): embedding alone precision 96% (44/46), recall 61% (44/72); keywords OR embedding precision 94% (47/50), recall 65% (47/72)
- 0.60: embedding alone precision 100% (34/34), recall 47% (34/72); keywords OR embedding precision 98% (41/42), recall 57% (41/72)
- 0.65: embedding alone precision 100% (19/19), recall 26% (19/72); keywords OR embedding precision 97% (34/35), recall 47% (34/72)
- 0.70: embedding alone precision 100% (10/10), recall 14% (10/72); keywords OR embedding precision 97% (30/31), recall 42% (30/72)

- message is sensitive at 0.45: precision 86% (60/70), recall 100% (60/60)
- message is sensitive at 0.50: precision 93% (55/59), recall 92% (55/60)
- message is sensitive at 0.55: precision 98% (47/48), recall 78% (47/60)
- message is sensitive at 0.60: precision 98% (40/41), recall 67% (40/60)
- message is sensitive at 0.65: precision 97% (33/34), recall 55% (33/60)
- message is sensitive at 0.70: precision 97% (29/30), recall 48% (29/60)

