# Sensitive-category detector review (Phase 6)

## Trigger

Berk's live test: a message "Yes i walk outside with my coffee" was stored as a private memory
with category `religion_politics`. "For 2 hours" was stored as `relationship`. Neither message is
about those topics.

## Cause

`CategoryDetector.detect` (src/hunch/privacy/categories.py) counts a category when the message's
embedding similarity to one of its prototype sentences is at least `prototype_min_similarity`
(0.45). Short, generic messages score about 0.40 to 0.48 against every category, so a generic
message can cross 0.45 for an unrelated category. The category stored for a memory is the first
hit, and any hit makes the memory `private`.

## Measurements

Two blind sets were written by a separate agent that saw no code and no earlier probe set:
`probes/blind_v2.json` (120 messages, 64 sensitive) and `probes/blind_v3.json` (120 messages, 60
sensitive). The everyday baseline `probes/neutral_v2.json` (40 sentences) was also written blind.

Message-level precision (a memory is private when at least one category hits) and sensitive
recall:

| Method | v2 precision | v2 recall | v3 precision | v3 recall |
|---|---|---|---|---|
| Raw similarity 0.45 (current) | 82% | 64/64 | 88% | 58/60 |
| Contrast minus everyday baseline, 0.00 | 82% | 64/64 | 75% | 60/60 |
| Contrast, 0.02 | 89% | 64/64 | 79% | 58/60 |
| Contrast, 0.04 | 88% | 63/64 | 83% (57/69) | 57/60 |
| Contrast, 0.08 | 95% | 61/64 | 92% (54/59) | 54/60 |

Category-level precision (for labels) on v3: raw 0.45 gives 48%; contrast 0.08 gives 49% with
recall 88%.

Contrast scoring looked better on v2 and worse on v3, so the v2 gain was specific to that set and
the threshold chosen on it. The contrast method is not adopted.

## Decision

- The privacy threshold stays at 0.45 (`config/hunch.toml`, `[privacy]`). It misses almost no
  sensitive message, and a false alarm only makes a general memory private, which is the safe side.
- Wrong category labels for generic messages are accepted as a known limit. The label is shown in
  the admin view and used only to name a category in the privacy question, which needs a keyword
  or a similarity of at least 0.50.
- The contrast method and the everyday prototypes are not in the code.

## Not done

- Using the category label less in privacy profile answers. This needs its own design look,
  because the profile answer applies to the categories a turn was tagged with.
- A model-based sensitivity judge. A separate design decision.

## Known misses at 0.45

- v2: none.
- v3: two sensitive messages are missed: "owe three different companies and I just avoid opening the envelopes" (money) and "my sister said she wishes i'd never been born, and i keep replaying it" (relationship). Both are implicit, with no keyword, and sit below the threshold.
