# Loop topic de-duplication probes (Phase 6)

Set: `eval/probes/loop_topics.json`, 60 pairs. Pairs with different names count as similarity 0 (the name rule).

Configured same_topic_similarity: 0.8. Lowest same-matter pair: 0.609; highest different pair: 0.786.

| threshold | same matter caught | different pairs merged |
| --- | --- | --- |
| 0.60 | 30/30 | 9/30 |
| 0.65 | 27/30 | 5/30 |
| 0.70 | 25/30 | 2/30 |
| 0.75 | 18/30 | 1/30 |
| 0.80 | 14/30 | 0/30 |
| 0.85 | 8/30 | 0/30 |
| 0.90 | 2/30 | 0/30 |

Closest different pairs:

- 0.786 dentist appointment / eye doctor visit
- 0.722 brother's birthday party / sister's wedding
- 0.697 mom's surgery / dad's check-up
- 0.692 ordering new laptop / laptop repair
- 0.687 salary negotiation / rent increase

Least similar same-matter pairs:

- 0.609 package delivery / waiting for the parcel
- 0.642 doctor's appointment / seeing the GP
- 0.645 flat viewing / apartment viewing on Saturday
- 0.665 wifi installation / internet technician visit
- 0.684 rent increase / landlord raising the rent
