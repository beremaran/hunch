| type | gold | strict P | strict R | lenient P | lenient R |
| --- | --- | --- | --- | --- | --- |
| person | 6 | 100% | 100% | 100% | 100% |
| place | 3 | 100% | 100% | 100% | 100% |
| song | 2 | 100% | 100% | 100% | 100% |
| film | 3 | 75% | 100% | 75% | 100% |
| date | 8 | 100% | 38% | 100% | 38% |
| emotion | 13 | 73% | 62% | 73% | 62% |
| phrase | 1 | 0% | 0% | 100% | 100% |
| overall | 36 | 83% | 69% | 87% | 72% |

Latency per message: median 2.58 s, max 4.99 s; retries: 0

Errors:
- h04 'I told Hope about the job offer last Monday and she cried happy tears.': extra ['emotion:joy'], missed ['date:2026-10-19']
- h07 'I keep thinking about Sherlock Holmes, I wish I was half as observant ': extra ['film:sherlock_holmes'], missed []
- h10 "I'm moving to Osaka next summer, still can't believe it!": extra [], missed ['emotion:excitement']
- h11 "Halloween party at Marcus's place, he's making everyone dress up as 90": extra [], missed ['date:halloween']
- h12 'Nobody has texted me all weekend and I just stared at the ceiling for ': extra ['emotion:sad'], missed []
- h13 "Can you remind me to call Dmitri on Feb 14? It's his birthday.": extra [], missed ['date:2027-02-14']
- h14 'Just passed my driving test!!! Finally!': extra [], missed ['emotion:pride']
- h17 "My boss moved the deadline to tomorrow and I haven't slept properly in": extra [], missed ['emotion:stress']
- h18 'Walked around Lake Geneva with my brother yesterday, it was so peacefu': extra [], missed ['date:2026-10-19']
- h19 'My grandpa used to hum Moon River while cooking. I miss him so much.': extra ['emotion:grief'], missed ['emotion:nostalgia', 'emotion:sad']
- h20 'We call our couch the big marshmallow, and Priya and I are binge-watch': extra ['phrase:big_marshmallow'], missed ['date:2026-10-22', 'phrase:the_big_marshmallow']
