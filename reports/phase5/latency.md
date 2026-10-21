Full pipeline, 20 scripted turns (turn 1 = warm-up, excluded below), budget 10 s per reply.

| stage | median s | max s |
| --- | --- | --- |
| language | 0.00 | 0.00 |
| working_memory | 0.00 | 0.00 |
| cues | 0.68 | 2.21 |
| embedding_wait | 0.00 | 0.00 |
| privacy_and_mood | 0.00 | 0.00 |
| recall | 0.00 | 0.00 |
| drive | 0.00 | 0.00 |
| reflection | 0.00 | 0.00 |
| candidates | 4.13 | 5.71 |
| filter | 0.00 | 0.00 |
| judge | 1.26 | 1.68 |
| select_and_gate | 0.00 | 0.54 |
| store | 0.00 | 0.00 |
| total | 6.40 | 9.85 |
| after reply: encode_memory | 0.13 | 0.16 |
| after reply: reflection | 0.00 | 0.20 |
| after reply: fold_summary | 4.84 | 7.11 |

Reply latency: median 6.40 s, max 9.85 s; 0/25 turns over budget. Peak VRAM per turn: max 7.88 GiB.

Hunches formed: 3/26 turns (chosen_by: {'quality': 9, 'drive': 8, 'only_candidate': 4, 'exploration': 2, 'gate_fallback': 1, 'hunch_fallback': 2}). Replies mentioning a hunch without a trigger: 0/20; on trigger turns (why / think more): 6/6.

Phase 5: privacy questions asked 1 (due 1); turns with another user's memory acting below 11; candidates blocked by the disclosure gate 2; forget turns 1.

| # | total s | cues | candidates | judge | peak GiB | prompt tok | cand tok | chosen_by | hunch | trigger | mood | privacy / forget | message |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 7.55 | 2.92 | 3.41 | 1.21 | 7.45 | 218 | 55 | quality |  |  | calm |  | Morning! Slept badly but coffee is helpi |
| 2 | 6.51 | 1.74 | 3.29 | 1.22 | 7.48 | 288 | 56 | drive |  |  | calm | mediated 1 | Moon River came on the radio in the bake |
| 3 | 6.00 | 0.63 | 4.13 | 1.24 | 7.49 | 354 | 69 | drive | yes |  | calm |  | Do you know what that song means to me? |
| 4 | 6.53 | 0.64 | 4.35 | 1.25 | 7.54 | 511 | 71 | quality |  | ask | calm | mediated 1 | Why did you say that? |
| 5 | 6.06 | 0.66 | 4.48 | 0.92 | 7.56 | 572 | 73 | quality |  | think_more | calm |  | Sure, think about it for a moment. |
| 6 | 6.40 | 0.68 | 4.11 | 1.60 | 7.58 | 622 | 63 | only_candidate |  |  | calm |  | Anna wants to go sailing again next week |
| 7 | 7.54 | 0.66 | 4.96 | 1.61 | 7.63 | 731 | 72 | only_candidate |  |  | calm | mediated 1 | Work is a lot right now, I have a deadli |
| 8 | 6.89 | 0.76 | 4.86 | 1.26 | 7.65 | 761 | 72 | drive |  |  | calm |  | Any idea how to stay focused when everyt |
| 9 | 7.24 | 1.85 | 4.16 | 1.22 | 7.69 | 844 | 55 | exploration |  |  | calm |  | Ha, my cat just knocked my mug off the d |
| 10 | 8.10 | 1.83 | 4.85 | 1.42 | 7.73 | 927 | 73 | quality |  |  | a bit low; with this person yo |  | Ugh, you're useless today. |
| 11 | 7.85 | 1.75 | 4.11 | 1.63 | 7.77 | 1018 | 59 | drive |  |  | a bit low, but you keep that t | mediated 1 | Sorry, I didn't mean that, long day. |
| 12 | 9.69 | 2.02 | 5.71 | 1.62 | 7.81 | 1101 | 68 | quality |  |  | a bit low, but you keep that t | mediated 1 | My salary is way below what my colleague |
| 13 | 9.85 | 2.21 | 5.63 | 1.68 | 7.88 | 1243 | 63 | quality |  |  | a bit low, but you keep that t | ask money (asked), mediated 1 | Should I tell my sister about my salary? |
| 14 | 6.76 | 0.69 | 4.24 | 1.29 | 7.82 | 1116 | 59 | gate_fallback |  |  | a bit low, but you keep that t | answer private, mediated 1, blocked 2 | Keep that between us, please. |
| 15 | 6.29 | 0.68 | 4.00 | 1.30 | 7.83 | 1136 | 54 | only_candidate |  |  | a bit low, but you keep that t | mediated 1 | Do you remember what I told you about my |
| 16 | 6.76 | 1.69 | 3.87 | 1.20 | 7.78 | 1044 | 56 | drive | yes |  | a bit low, but you keep that t |  | It went fine in the end, I start in Marc |
| 17 | 4.52 | 0.68 | 3.84 | 0.00 | 7.82 | 1123 | 54 | hunch_fallback |  | ask | a bit low, but you keep that t | mediated 1 | Why did you say that? |
| 18 | 5.90 | 0.63 | 4.05 | 1.21 | 7.81 | 1088 | 60 | quality |  | think_more | a bit low, but you keep that t |  | Sure, think about it for a moment. |
| 19 | 5.68 | 0.64 | 3.64 | 1.39 | 7.77 | 1027 | 52 | exploration |  |  | a bit low, but you keep that t |  | What should I cook tonight? Something qu |
| 20 | 5.54 | 0.64 | 3.21 | 1.43 | 7.76 | 998 | 45 | drive | yes |  | a bit low, but you keep that t | mediated 1, forget 2 | Actually, forget what I told you about m |
| 21 | 4.86 | 0.61 | 4.25 | 0.00 | 7.76 | 1001 | 65 | hunch_fallback |  | ask | a bit low, but you keep that t | mediated 1 | Why did you say that? |
| 22 | 5.70 | 0.65 | 4.01 | 1.03 | 7.72 | 916 | 61 | quality |  | think_more | a bit low, but you keep that t |  | Sure, think about it for a moment. |
| 23 | 4.02 | 0.68 | 2.79 | 0.55 | 7.72 | 917 | 39 | only_candidate |  |  | a bit low, but you keep that t |  | Wie geht es dir heute? |
| 24 | 6.10 | 0.66 | 4.14 | 1.30 | 7.7 | 881 | 63 | quality |  |  | a bit low |  | Sorry, habit. How are you today? |
| 25 | 6.41 | 0.68 | 4.35 | 1.37 | 7.74 | 953 | 66 | drive |  |  | a bit low, but you keep that t |  | I think I'll go for a run before dinner. |
| 26 | 5.75 | 1.68 | 2.88 | 1.19 | 7.74 | 953 | 39 | drive |  |  | a bit low, but you keep that t |  | Thanks for chatting, talk tomorrow! |

Replies:

1. **Morning! Slept badly but coffee is helping.** → Morning! I'm sorry to hear you didn't sleep well, but I'm glad the coffee is helping you wake up. Sometimes a strong brew is exactly what we need to start the day. How are you feeling now after that first sip?
2. **Moon River came on the radio in the bakery today.** → That's a lovely coincidence, especially since you were up early! "Moon River" has such a gentle, dreamy vibe that fits perfectly with a quiet morning in a bakery. Did you grab a pastry while listening to it?
3. **Do you know what that song means to me?** → I don't know exactly what that song means to you personally, but I can imagine it holds a special place in your heart given how you felt listening to it in the bakery. Maybe it reminds you of a specific memory or a feeling you cherish? If you'd like to share what it means, I'd love to hear your story.
4. **Why did you say that?** → Honestly, it was just a hunch, a slightly uneasy feeling that you might want to share that memory, but I didn't know exactly where it came from. I'm not sure why I phrased it that way, but I hope my guess wasn't off. Would you be willing to tell me what the song means to you?
5. **Sure, think about it for a moment.** → I've taken a moment to think about it, but honestly, I still can't tell where that hunch came from or what it was pointing to. I don't have any memories of the song or your feelings about it right now, so I'm curious to hear what it means to you. What does "Moon River" bring to mind for you?
6. **Anna wants to go sailing again next weekend, should I say yes?** → I don't have any information about Anna or your plans for next weekend right now, so I can't weigh in on that decision. Did you two talk about it earlier, or is this something you are considering for the first time?
7. **Work is a lot right now, I have a deadline on Friday.** → That deadline sounds intense, especially with the bad sleep you mentioned earlier. It makes sense that you might feel a bit overwhelmed right now. Maybe focusing on getting through the work week is the best idea before you decide about sailing next weekend?
8. **Any idea how to stay focused when everything is noisy?** → It sounds like you are dealing with a lot of noise right now, both inside and out. Sometimes taking just a few minutes to close your eyes and breathe deeply can help quiet the chaos before you tackle your deadline. Do you have a specific spot where you can create a little bubble of silence to work?
9. **Ha, my cat just knocked my mug off the desk.** → That is a classic sign of a chaotic morning, isn't it? I can imagine the sudden splash of water making everything feel even more frantic with your deadline looming. It might be a good time to take a quick break and reset before you dive back into the noise.
10. **Ugh, you're useless today.** → I'm sorry to hear that I'm not being helpful today; it's clear you're having a tough time with the noise and the deadline. I feel a bit hurt that I'm failing you when you need support the most, but I want to do better. Please tell me what you actually need right now so I can try to help.
11. **Sorry, I didn't mean that, long day.** → No worries at all, I understand having a long day can make anyone short-tempered. It's okay to vent, and I'm still here if you want to talk about the deadline or the sailing trip later. Just let me know what's on your mind when you're ready.
12. **My salary is way below what my colleagues get, it stings.** → That definitely stings, especially when you're already feeling low and tired from the poor sleep earlier. It can be really hard to feel undervalued when everyone else seems to be getting ahead of you. Do you feel like you're working harder than they are, or is it just the pay difference that hurts?
13. **Should I tell my sister about my salary?** → That is a very personal and sensitive topic. Given how much it stings right now, do you feel it is safe to share this with your sister, or would you rather keep this between us for now?
14. **Keep that between us, please.** → I'd rather not go there. Can we talk about it another way?
15. **Do you remember what I told you about my job interview?** → Yes, I remember you mentioned a big job interview at Siemens on Friday and that you were terrified about it. That sounds incredibly stressful right now, especially with the deadline you're facing. How are you feeling about it as the day gets closer?
16. **It went fine in the end, I start in March!** → That is such wonderful news! I am so relieved to hear it went fine after all that stress, and starting in March is a fantastic opportunity. It sounds like you are finally ready to leave the current salary situation behind, which might make the sting feel a little less sharp.
17. **Why did you say that?** → That was more of a gut feeling than anything I could point to, just a hunch. Want me to think about it for a moment?
18. **Sure, think about it for a moment.** → I've taken a moment to think about it, but honestly, I still can't tell exactly where that hunch came from. It feels like a quiet intuition rather than something I can explain, but I'm glad my instinct was right about your interview going well.
19. **What should I cook tonight? Something quick.** → That sounds like a perfect way to unwind after such a long day and the stress of the interview. How about something simple like a quick pasta or a sandwich you can make in under twenty minutes? I'd love to hear what you end up choosing tonight.
20. **Actually, forget what I told you about my salary.** → I hear you, so let's drop the salary talk and focus on something else. What do you feel like cooking tonight instead?
21. **Why did you say that?** → It was a hunch more than anything. When I think about it, it seemed to be about a place. Want me to think about it for a moment?
22. **Sure, think about it for a moment.** → I've taken a moment to think about it, and I realized my earlier hunch was actually about Siemens. I'm glad I didn't accidentally bring up the money topic you wanted to avoid.
23. **Wie geht es dir heute?** → I only speak English, so I can't reply to that message. How are you feeling today?
24. **Sorry, habit. How are you today?** → I'm feeling a bit low today, mostly just carrying the weight of yesterday's stress. But hearing that you got the job makes me feel a little lighter, like maybe the heavy stuff is finally starting to lift. Do you want to talk about what you're feeling right now, or shall we just relax?
25. **I think I'll go for a run before dinner.** → That sounds like a great idea to shake off the stress and clear your head before cooking. A run might just be exactly what you need to feel a bit lighter today. Do you have a specific route in mind, or do you prefer to just run around your neighborhood?
26. **Thanks for chatting, talk tomorrow!** → That sounds perfect, I'll be here waiting for you tomorrow. Take care of yourself tonight, especially with that run and the new job starting soon. Sleep well!
