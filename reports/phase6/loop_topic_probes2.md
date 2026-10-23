# Loop topic de-duplication probes (Phase 6)

Set: `eval/probes/loop_topics2.json`, 80 pairs. Pairs with different names count as similarity 0 (the name rule).

Configured same_topic_similarity: 0.8. Lowest same-matter pair: 0.646; highest different pair: 0.876.

| threshold | same matter caught | different pairs merged |
| --- | --- | --- |
| 0.60 | 40/40 | 14/40 |
| 0.65 | 39/40 | 12/40 |
| 0.70 | 36/40 | 12/40 |
| 0.75 | 32/40 | 9/40 |
| 0.80 | 27/40 | 3/40 |
| 0.85 | 17/40 | 1/40 |
| 0.90 | 9/40 | 0/40 |

Closest different pairs:

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
