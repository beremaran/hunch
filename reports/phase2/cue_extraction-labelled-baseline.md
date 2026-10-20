| type | gold | strict P | strict R | lenient P | lenient R |
| --- | --- | --- | --- | --- | --- |
| person | 7 | 47% | 100% | 47% | 100% |
| place | 7 | 100% | 100% | 100% | 100% |
| song | 3 | 100% | 100% | 100% | 100% |
| film | 5 | 100% | 80% | 100% | 80% |
| date | 11 | 67% | 36% | 67% | 36% |
| emotion | 19 | 100% | 53% | 100% | 53% |
| phrase | 2 | 100% | 100% | 100% | 100% |
| overall | 54 | 79% | 69% | 79% | 69% |

Latency per message: median 2.56 s, max 5.2 s; retries: 0

Errors:
- c01 "Just booked flights to Lisbon for Friday! Can't wait to see Anna again": extra [], missed ['date:2026-10-23', 'emotion:excitement']
- c03 'Been listening to Hallelujah on repeat all evening. Makes me think of ': extra ['person:grandpa'], missed ['emotion:nostalgia']
- c04 'Watched Dune last night with my mum, she fell asleep in the first twen': extra ['person:mum'], missed []
- c07 'I got the job!! Starting Monday at the new place.': extra [], missed ['date:2026-10-26']
- c08 "My dad's surgery is tomorrow morning and I can't sleep.": extra ['person:dad'], missed ['date:2026-10-21', 'emotion:tired']
- c11 'Do you know Bohemian Rhapsody? Freddy would be proud of my karaoke las': extra ['person:freddy'], missed []
- c14 "My birthday is on March 3rd and I still haven't planned anything.": extra ['date:2026-03-03'], missed ['date:2027-03-03']
- c17 'Grandma passed away last spring and today I found her old recipe book.': extra [], missed ['emotion:grief']
- c18 "Christmas at my sister's again this year, I'm dreading it already.": extra [], missed ['date:christmas', 'emotion:anxious']
- c20 'Have you seen The Office? Michael Scott cracks me up. Also Jordan is b': extra ['person:dwight', 'person:michael_scott'], missed []
- c21 "My doctor said my blood pressure is fine, so that's a relief.": extra [], missed ['emotion:calm']
- c22 'Thanks for listening yesterday, it really helped.': extra [], missed ['date:2026-10-19', 'emotion:gratitude']
- c26 'Shaun of the Dead is my comfort film. Watching it again, alone, as usu': extra [], missed ['emotion:lonely']
- c28 "I'm so proud of my little brother, he ran his first marathon in Berlin": extra ['date:2026-10-11', 'person:little_brother'], missed ['date:2026-10-18']
- c30 'Remember Amelie? I rewatched it and cried at the end, Mum loved it so ': extra ['person:amelie'], missed ['emotion:nostalgia', 'film:amelie']
