# Relevance gate on the blind set (shared cue OR cosine)

60 pairs (30 relevant). Cosine: relevant median 0.486 (min 0.204), not relevant median 0.325 (max 0.592).

| threshold | precision | recall | tp | fp | fn | tn |
| --- | --- | --- | --- | --- | --- | --- |
| 0.30 | 60% | 93% | 28 | 19 | 2 | 11 |
| 0.35 | 69% | 90% | 27 | 12 | 3 | 18 |
| 0.40 | 71% | 83% | 25 | 10 | 5 | 20 |
| 0.45 (config) | 80% | 67% | 20 | 5 | 10 | 25 |
| 0.50 | 79% | 50% | 15 | 4 | 15 | 26 |
| 0.55 | 80% | 27% | 8 | 2 | 22 | 28 |
| 0.60 | 71% | 17% | 5 | 2 | 25 | 28 |

## Wrong at 0.45

- missed (0.403): 'ok interview is tomorrow, wish me luck' / 'They said: "applying to the data analyst role at Brightline, been prepping for weeks"'
- missed (0.434): 'she said yes!!!' / 'They said: "going to ask Priya to move in with me this weekend, terrified"'
- let through (0.537): 'Tom sent me the funniest meme lol' / 'They said: "Tom\'s girlfriend flirted with me at his birthday and i dont know what to do"'
- missed (0.418): 'the vet called, results are fine' / 'They said: "Biscuit has been throwing up since tuesday, taking him in on friday"'
- missed (0.27): 'back from the trip, the food was unreal' / 'They said: "flying to Lisbon on the 12th for my sister\'s birthday"'
- let through (0.592, shared cue): 'Anna just texted me a picture of her new haircut lol' / 'They said: "Anna had surgery in the spring and the recovery took forever"'
- missed (0.37): "what's a good gift for my wife? 10 years married" / 'They said: "our 10th anniversary is on the 22nd and i have no idea what to do"'
- missed (0.413): 'i got the keys!!' / 'They said: "closing on the house on friday, mortgage finally approved"'
- let through (0.463, shared cue): 'Priya loves sushi, where should we go for her bday?' / 'They said: "Priya\'s visa runs out in March and we\'re both worried"'
- missed (0.32): 'what should I cook for the dinner party?' / 'They said: "i\'m hosting 6 people on saturday, one of them is vegan"'
- missed (0.396): 'so is it better to go with python or js for a first language?' / 'They said: "want to switch careers into programming, thinking of a bootcamp"'
- let through (0.477): 'bank holiday plans?' / 'They said: "opened an account at a new bank to save for a house"'
- missed (0.407): 'he did it again, forgot our plans' / 'They said: "my boyfriend Marc keeps cancelling on me last minute and i\'m tired of it"'
- missed (0.204): 'banana bread recipe pls' / 'They said: "i\'m allergic to walnuts, ended up in the ER once"'
- let through (0.501): 'thinking about quitting social media' / 'They said: "i quit smoking in January and it\'s going okay"'
