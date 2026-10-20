| type | gold | strict P | strict R | lenient P | lenient R |
| --- | --- | --- | --- | --- | --- |
| person | 9 | 90% | 100% | 90% | 100% |
| place | 9 | 100% | 100% | 100% | 100% |
| song | 3 | 100% | 100% | 100% | 100% |
| film | 5 | 100% | 100% | 100% | 100% |
| date | 30 | 100% | 100% | 100% | 100% |
| emotion | 23 | 78% | 61% | 78% | 61% |
| phrase | 0 | - | - | - | - |
| overall | 79 | 93% | 89% | 93% | 89% |

Latency per message: median 2.98 s, max 6.12 s; retries: 0

Errors:
- h2-06 "just finished watching succession and wow, i'm still processing": extra ['emotion:anxious'], missed ['emotion:surprise']
- h2-08 "in two days i start my new job and i'm so nervous": extra [], missed ['emotion:anxious']
- h2-11 "i've been so tired lately, barely sleeping": extra ['emotion:anxious'], missed []
- h2-14 'going to see the cure in berlin on nov 20': extra ['person:the_cure'], missed []
- h2-19 'my doctor said i should rest for a few days, bit worried honestly': extra [], missed ['emotion:worry']
- h2-23 'i got the promotion!! so proud right now': extra [], missed ['emotion:joy']
- h2-24 "hotel california came on today and it reminds me of my dad's road trip": extra [], missed ['emotion:nostalgia']
- h2-28 "we're getting a puppy in 10 days!": extra [], missed ['emotion:excitement']
- h2-36 'thinking about moving to amsterdam next year, scared but excited': extra [], missed ['emotion:excitement', 'emotion:fear']
- h2-37 'the pumpkin soup on halloween was so good, ben outdid himself': extra ['emotion:joy'], missed []
- h2-38 "my brother and sister are coming for easter, i'll cook everything": extra ['emotion:excitement'], missed []
- h2-40 'put on purple rain tonight, love both the song and the film': extra [], missed ['emotion:love']
