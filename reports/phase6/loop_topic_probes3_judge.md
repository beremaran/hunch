# Loop topic de-duplication probes (Phase 6)

Set: `eval/probes/loop_topics3.json`, 100 pairs. Pairs with different names count as similarity 0 (the name rule), and so do pairs the model judge calls different.

Configured same_topic_similarity: 0.8. Lowest same-matter pair: 0.000; highest different pair: 0.000 (after the judge).

| threshold | same matter caught | different pairs merged |
| --- | --- | --- |
| 0.55 | 48/50 | 0/50 |
| 0.60 | 48/50 | 0/50 |
| 0.65 | 46/50 | 0/50 |
| 0.70 | 42/50 | 0/50 |
| 0.75 | 36/50 | 0/50 |
| 0.80 | 30/50 | 0/50 |
| 0.85 | 22/50 | 0/50 |
| 0.90 | 8/50 | 0/50 |

Judge alone: 99/100 right. Wrong:

- visa application / visa appointment (same: True, judge: False, similarity 0.797)

Closest different pairs (similarity before the judge):

- 0.925 dog's vet checkup / cat's vet checkup
- 0.917 camping trip with Jonas / hiking trip with Jonas
- 0.890 Tom and Laura's wedding / Tom and Sara's wedding
- 0.888 dentist appointment / eye doctor appointment
- 0.872 sister's wedding / sister's visit

Least similar same-matter pairs:

- 0.490 the new sofa arriving / couch delivery
- 0.616 exam / chemistry final on Monday
- 0.636 tooth extraction / dentist appointment
- 0.674 flu recovery / getting over the flu
- 0.680 flat viewing on Saturday / viewing the apartment this weekend
