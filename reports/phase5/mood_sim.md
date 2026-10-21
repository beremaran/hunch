# Mood simulation (Phase 5)

Real config, pure functions of `hunch.mood.state`, seed 2026, 30 days. Regenerate with `python -m scripts.simulate_mood`.

## What each user was told

- A, right after the third hostile message (day 0 09:09): hurt 0.90 >= hurt_label 0.3, so the mood is shown: "a bit low and tense; with this person you feel a little hurt".
- B at 09:10 (closeness 0.20, masked): "a bit low and tense, but you keep that to yourself in this conversation" (mood v=-0.45, a=0.76, e=0.52; label without masking text: a bit low and tense).
- B at 12:00 (masked): "a bit low, but you keep that to yourself in this conversation" (v=-0.23, a=0.63, e=0.51).
- B at 18:00, before the joy message counts (masked): "calm" (v=-0.06).
- Lowest global valence in the first 48 h (hourly samples): -0.37.

## Drive terms toward B at day 0 09:10 (added to the drive vector)

| | warmth | caution | energy | curiosity |
|---|---|---|---|---|
| shown | -0.135 | +0.090 | +0.006 | +0.035 |
| masked (mask_leak 0.2) | -0.027 | +0.018 | +0.001 | +0.031 |

B's relationship is still at its start values at 09:10, so only the curiosity baseline (0.1 x (0.5 - 0.2) = +0.030) and the mood part are non-zero.

## A's hurt

- Hurt after the three hostile messages: 0.90.
- Hurt just before / after A's apology at day 3 10:00: 0.67 / 0.33.
- First time A's hurt is below hurt_label (0.3), with the apology: day 4 11:28 (4.5 days after day 0 00:00).
- Same, without any apology: day 11 11:28 (11.5 days after day 0 00:00).

## When the mood becomes visible by closeness alone

- show_closeness = 0.6. A reaches it: never; B reaches it: never.

## State at day 30

- A: trust 0.58, closeness 0.48, hurt 0.02
- B: trust 0.77, closeness 0.58, hurt 0.00
- global mood: v=+0.05, a=0.52, e=0.52 -> calm

Plots: `mood_sim_global.png`, `mood_sim_relationships.png`, `mood_sim_drive.png`.
