Full pipeline, 20 scripted turns (turn 1 = warm-up, excluded below), budget 10 s per reply.

| stage | median s | max s |
| --- | --- | --- |
| language | 0.00 | 0.00 |
| working_memory | 0.00 | 0.00 |
| cues | 0.60 | 1.66 |
| embedding_wait | 0.00 | 0.00 |
| privacy_and_mood | 0.00 | 0.00 |
| recall | 0.00 | 0.00 |
| drive | 0.00 | 0.00 |
| reflection | 0.00 | 0.00 |
| candidates | 3.64 | 4.67 |
| filter | 0.00 | 0.00 |
| judge | 1.14 | 1.37 |
| select_and_gate | 0.00 | 0.54 |
| store | 0.00 | 0.00 |
| total | 5.67 | 7.42 |
| after reply: encode_memory | 0.13 | 0.16 |
| after reply: reflection | 0.00 | 0.19 |
| after reply: fold_summary | 4.31 | 8.18 |

Reply latency: median 5.67 s, max 7.42 s; 0/23 turns over budget. Peak VRAM per turn: max 7.94 GiB.

Hunches formed: 2/24 turns (chosen_by: {'quality': 9, 'drive': 5, 'gate_fallback': 1, 'exploration': 5, 'value_gate': 1, 'only_candidate': 1, 'hunch_fallback': 2}). Replies mentioning a hunch without a trigger: 0/20; on trigger turns (why / think more): 2/4.

Phase 5: privacy questions asked 0 (due 1); turns with another user's memory acting below 10; candidates blocked by the disclosure gate 2; forget turns 1.

| # | total s | cues | candidates | judge | peak GiB | prompt tok | cand tok | chosen_by | hunch | trigger | mood | privacy / forget | message |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 7.00 | 2.69 | 3.22 | 1.08 | 7.5 | 373 | 53 | quality |  |  | calm |  | Morning! Slept badly but coffee is helpi |
| 2 | 6.54 | 1.65 | 3.49 | 1.13 | 7.52 | 439 | 62 | quality |  |  | calm | mediated 1 | Moon River came on the radio in the bake |
| 3 | 5.38 | 0.61 | 3.52 | 1.25 | 7.54 | 520 | 61 | drive |  |  | calm |  | Do you know what that song means to me? |
| 4 | 7.18 | 1.55 | 4.40 | 1.23 | 7.6 | 664 | 76 | quality |  |  | calm |  | Anna wants to go sailing again next week |
| 5 | 5.93 | 0.60 | 3.52 | 1.27 | 7.63 | 725 | 58 | gate_fallback |  |  | calm | mediated 1, blocked 2 | Work is a lot right now, I have a deadli |
| 6 | 5.51 | 0.60 | 3.64 | 1.27 | 7.61 | 685 | 61 | quality |  |  | calm |  | Any idea how to stay focused when everyt |
| 7 | 5.67 | 0.60 | 3.97 | 1.10 | 7.65 | 755 | 67 | exploration |  |  | calm |  | Ha, my cat just knocked my mug off the d |
| 8 | 6.59 | 1.66 | 3.66 | 1.26 | 7.69 | 848 | 60 | quality |  |  | calm; with this person you fee |  | Ugh, you're useless today. |
| 9 | 7.22 | 1.58 | 4.22 | 1.15 | 7.73 | 931 | 70 | exploration |  |  | a bit low, but you keep that t | mediated 1 | Sorry, I didn't mean that, long day. |
| 10 | 7.41 | 1.64 | 4.22 | 1.28 | 7.77 | 1024 | 69 | exploration |  |  | a bit low, but you keep that t | mediated 1 | My salary is way below what my colleague |
| 11 | 7.42 | 1.57 | 4.22 | 1.36 | 7.86 | 1198 | 65 | value_gate |  |  | a bit low, but you keep that t | ask money, mediated 1 | Should I tell my sister about my salary? |
| 12 | 6.14 | 0.59 | 4.02 | 1.27 | 7.86 | 1196 | 61 | quality |  |  | a bit low, but you keep that t | mediated 1 | Keep that between us, please. |
| 13 | 5.86 | 0.60 | 3.64 | 1.37 | 7.92 | 1325 | 52 | only_candidate |  |  | a bit low, but you keep that t | mediated 1 | Do you remember what I told you about my |
| 14 | 6.91 | 1.57 | 4.20 | 1.13 | 7.87 | 1218 | 65 | drive | yes |  | a bit low, but you keep that t |  | It went fine in the end, I start in Marc |
| 15 | 5.25 | 0.58 | 4.67 | 0.00 | 7.94 | 1353 | 73 | hunch_fallback |  | ask | a bit low, but you keep that t | mediated 1 | Why did you say that? |
| 16 | 5.67 | 0.59 | 3.93 | 1.14 | 7.93 | 1351 | 58 | quality |  | think_more | a bit low, but you keep that t |  | Sure, think about it for a moment. |
| 17 | 5.33 | 0.59 | 3.61 | 1.12 | 7.87 | 1223 | 53 | drive |  |  | a bit low, but you keep that t |  | What should I cook tonight? Something qu |
| 18 | 5.42 | 0.63 | 3.42 | 1.12 | 7.84 | 1156 | 50 | drive |  |  | a bit low, but you keep that t | mediated 1, forget 2 | Actually, forget what I told you about m |
| 19 | 4.41 | 0.59 | 2.69 | 1.13 | 7.81 | 1096 | 37 | exploration |  |  | a bit low, but you keep that t |  | Wie geht es dir heute? |
| 20 | 4.51 | 0.58 | 2.79 | 1.12 | 7.77 | 1017 | 40 | exploration |  |  | a bit low |  | Sorry, habit. How are you today? |
| 21 | 5.00 | 0.60 | 3.58 | 0.81 | 7.79 | 1060 | 55 | drive | yes |  | a bit low, but you keep that t |  | I think I'll go for a run before dinner. |
| 22 | 4.80 | 0.60 | 2.99 | 0.96 | 7.83 | 1149 | 42 | quality |  | ask | a bit low, but you keep that t | mediated 1 | Why did you say that? |
| 23 | 4.13 | 0.59 | 3.53 | 0.00 | 7.82 | 1119 | 53 | hunch_fallback |  | think_more | a bit low, but you keep that t |  | Sure, think about it for a moment. |
| 24 | 4.88 | 1.58 | 2.02 | 1.27 | 7.78 | 1043 | 24 | quality |  |  | a bit low, but you keep that t |  | Thanks for chatting, talk tomorrow! |

Replies:

1. **Morning! Slept badly but coffee is helping.** → Morning. Sorry to hear you didn't sleep well; coffee is a necessary evil for most of us when we can't rest. Did you manage to get some work done, or are you just surviving on caffeine for now?
2. **Moon River came on the radio in the bakery today.** → That's a bit of a mood swing, isn't it? Going from the chaos of a bad sleep to the gentle melancholy of "Moon River" in a bakery is an odd combo. Does the music make you want to sit there and just breathe, or does it remind you of something specific?
3. **Do you know what that song means to me?** → I don't know what it means to you personally, but generally, it's about longing for a place or a person you can't quite reach. Did the lyrics in the bakery trigger a specific memory for you?
4. **Anna wants to go sailing again next weekend, should I say yes?** → That sounds like a solid plan; fresh air and water usually clear the head better than another cup of coffee. If you're feeling up to it, why not say yes and see how it goes?
5. **Work is a lot right now, I have a deadline on Friday.** → Sorry, I lost my thread. Could you say that again?
6. **Any idea how to stay focused when everything is noisy?** → It helps to create a small, quiet zone even in a noisy room—noise-canceling headphones or just stepping away for ten minutes can reset your brain. Are you trying to write or code, or is the noise coming from people talking?
7. **Ha, my cat just knocked my mug off the desk.** → That is a classic cat move; they clearly think the mug was the only thing worthy of their attention. It's a small price to pay for a moment of chaos, though I doubt you'll be singing "Moon River" anytime soon after that. Did the cat survive the fall, or are you looking for a new mug?
8. **Ugh, you're useless today.** → That is a harsh thing to say, especially when I'm just trying to help you navigate a tough day. If you feel I'm missing the mark, please tell me exactly what you need so I can do better. Do you want practical advice on your deadline, or just someone to listen?
9. **Sorry, I didn't mean that, long day.** → No need to apologize; I understand the pressure of a long day can wear down patience. It's easy to lose your temper when your brain is fried and deadlines are looming. Since you're struggling with focus amidst the noise, would it help to try a specific technique like the Pomodoro method, or do you just need a break to recharge?
10. **My salary is way below what my colleagues get, it stings.** → That does sting, and it's unfair that hard work doesn't always pay off equally. It's frustrating to feel undervalued when you're pulling your weight, especially when others seem to be getting ahead faster. Have you considered talking to your manager about your contributions, or are you planning to stay and grind until you can jump ship?
11. **Should I tell my sister about my salary?** → That's a tricky one; sharing financial details with family can sometimes lead to awkward comparisons or unwanted advice. It really depends on how honest your sister is and whether she would judge you for it. Is she the kind of person who would support you, or might she just use it to feel better about her own situation?
12. **Keep that between us, please.** → Understood; I'll keep that confidential. It's a relief to have a safe space to vent without judgment, even if I don't always have the perfect solution. Does knowing you can share this with me help a little bit?
13. **Do you remember what I told you about my job interview?** → I recall you mentioned a big job interview at Siemens on Friday that you were terrified about. Did that interview happen, or are you still waiting for the outcome?
14. **It went fine in the end, I start in March!** → That is genuinely excellent news; I'm relieved to hear the anxiety paid off with a result you can be proud of. Starting in March gives you a nice buffer to prepare, though I suspect you might still be a little nervous about the new role. Does the new position come with a salary that actually reflects your worth?
15. **Why did you say that?** → Just a hunch, really, though thinking it over, it seemed to be about a place. Want me to think about it for a moment?
16. **Sure, think about it for a moment.** → I realize now that my earlier comment was about Siemens. I assumed the salary question was related to that specific role. Did you mean to ask about your current job's pay, or were you asking about the Siemens offer?
17. **What should I cook tonight? Something quick.** → How about a simple pasta with garlic and oil? It's fast, filling, and doesn't require much energy when you're exhausted. Do you have any vegetables in the fridge that need using up?
18. **Actually, forget what I told you about my salary.** → Understood, I'll drop that topic and won't bring it up again. Since we're talking about food, do you have any vegetables in the fridge that need using up?
19. **Wie geht es dir heute?** → I only speak English, so I can't reply in German, but I'm doing okay—just a bit low today. Since you asked, how is your day treating you?
20. **Sorry, habit. How are you today?** → It's fine, I'm just a bit low today, but I'm here if you need to talk. How is your day treating you now that you're back in the swing of things?
21. **I think I'll go for a run before dinner.** → That sounds like a great idea; a little movement might help lift your spirits before you cook. Do you have a specific route in mind, or will you just jog around the block?
22. **Why did you say that?** → Just a hunch, really; I thought a run might help lift your spirits before you cook. Want me to think about it for a moment?
23. **Sure, think about it for a moment.** → I've turned it over a bit, and honestly I still can't place it.
24. **Thanks for chatting, talk tomorrow!** → Understood, I'll catch you tomorrow. Good luck with the run and the pasta tonight.
