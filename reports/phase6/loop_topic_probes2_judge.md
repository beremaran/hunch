# Loop topic de-duplication probes (Phase 6)

Set: `eval/probes/loop_topics2.json`, 80 pairs. Pairs with different names count as similarity 0 (the name rule), and so do pairs the model judge calls different.

Configured same_topic_similarity: 0.8. Lowest same-matter pair: 0.000; highest different pair: 0.000 (after the judge).

| threshold | same matter caught | different pairs merged |
| --- | --- | --- |
| 0.60 | 38/40 | 0/40 |
| 0.65 | 37/40 | 0/40 |
| 0.70 | 34/40 | 0/40 |
| 0.75 | 30/40 | 0/40 |
| 0.80 | 25/40 | 0/40 |
| 0.85 | 16/40 | 0/40 |
| 0.90 | 8/40 | 0/40 |

Judge alone: 78/80 right. Wrong:

- Spotify offer / job offer from Spotify (same: True, judge: False, similarity 0.815)
- Anna's birthday / Anna's birthday gift (same: True, judge: False, similarity 0.935)

Closest different pairs (similarity before the judge):

- 0.876 renting a flat / buying a flat
- 0.824 knee pain / back pain
- 0.806 piano lessons / guitar lessons
- 0.800 math exam / physics exam
- 0.778 buying a bike / repairing the bike

Least similar same-matter pairs:

- 0.646 new couch / sofa shopping
- 0.655 landlord deposit / getting the deposit back
- 0.673 job interview / interview next Tuesday
- 0.697 dentist appointment / teeth cleaning visit
- 0.712 flight to Lisbon / the flight next week
