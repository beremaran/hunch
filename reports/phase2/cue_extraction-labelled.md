| type | gold | strict P | strict R | lenient P | lenient R |
| --- | --- | --- | --- | --- | --- |
| person | 7 | 70% | 100% | 70% | 100% |
| place | 7 | 100% | 100% | 100% | 100% |
| song | 3 | 100% | 100% | 100% | 100% |
| film | 5 | 100% | 80% | 100% | 80% |
| date | 11 | 100% | 82% | 100% | 82% |
| emotion | 19 | 93% | 74% | 93% | 74% |
| phrase | 2 | - | 0% | - | 0% |
| overall | 54 | 92% | 81% | 92% | 81% |

Latency per message: median 2.63 s, max 5.73 s; retries: 0

Errors:
- c03 'Been listening to Hallelujah on repeat all evening. Makes me think of ': extra [], missed ['emotion:nostalgia']
- c07 'I got the job!! Starting Monday at the new place.': extra [], missed ['date:2026-10-26']
- c08 "My dad's surgery is tomorrow morning and I can't sleep.": extra [], missed ['emotion:anxious']
- c11 'Do you know Bohemian Rhapsody? Freddy would be proud of my karaoke las': extra ['person:freddy'], missed []
- c13 'We always do taco Tuesday at our place, and I burned everything again.': extra ['emotion:shame'], missed ['phrase:taco_tuesday']
- c21 "My doctor said my blood pressure is fine, so that's a relief.": extra [], missed ['emotion:calm']
- c22 'Thanks for listening yesterday, it really helped.': extra [], missed ['date:2026-10-19']
- c25 "'Locked Out of Heaven' came on at the gym and I got goosebumps. Bruno ": extra ['person:bruno_mars'], missed []
- c26 'Shaun of the Dead is my comfort film. Watching it again, alone, as usu': extra [], missed ['emotion:lonely']
- c27 "Our group chat is called the Wolfpack and we're meeting at The Rusty A": extra [], missed ['phrase:the_wolfpack']
- c30 'Remember Amelie? I rewatched it and cried at the end, Mum loved it so ': extra ['person:amelie'], missed ['emotion:nostalgia', 'film:amelie']
