| lang | prompts | samples | clean | wrong_lang | cjk_leak | list_format | missed_followup | no_privacy_question | unrequested_privacy_question | invented_memory | no_memory_admission | missing | denies_memory_system |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| en | 17 | 51 | 49 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 |

Full reply latency (pipeline), worst run per prompt: median 6.0 s, max 9.0 s; 0/17 over the 10 s budget.

Pipeline: 0/51 replies were the filter fallback (all candidates rejected), 0 the value-gate fallback; 3 of 153 candidates rejected by the filter.

### en-casual-01 (3/3 clean, 9.043 s)
- [0] (clean; quality) Morning! That's a fantastic choice; *Project Hail Mary* is a brilliant mix of science and heart. Since you loved that, have you tried *The Martian* by Andy Weir? It shares a similar spirit of problem-solving and survival in space. I think you'd really enjoy the way it balances humor with technical details.
- [1] (clean; quality) Morning! That's a fantastic choice, *Project Hail Mary* is such a clever mix of science and humor. Since you enjoyed that blend, have you considered *The Martian*? It's also by Andy Weir and shares that same spirit of problem-solving and wit. Let me know if you think you're ready for another survival story, or if you'd prefer something with a different vibe!
- [2] (clean; quality) Morning! That's a fantastic choice; Project Hail Mary is such a fun and clever book. Since you loved that mix of science and humor, maybe you'd enjoy The Martian by Andy Weir? It has a similar vibe where the protagonist uses pure ingenuity to survive. What kind of genres do you usually enjoy when you're looking for your next adventure?

### en-casual-02 (3/3 clean, 5.985 s)
- [0] (clean; quality) Honestly, I think pineapple on pizza is a bold choice that divides people deeply. While some argue the sweetness balances the salty cheese perfectly, I find myself leaning toward the idea that it disrupts the savory harmony of the dish. It's not that I hate fruit, but I just prefer my toppings to stay in their own lane. What do you think makes it work or fail for you?
- [1] (clean; quality) Honestly, I'm a bit torn on pineapple on pizza. I get that the sweetness of the fruit can balance out spicy or salty ingredients, but I personally prefer the classic combination of cheese and tomato sauce. What about you, do you love it or hate it?
- [2] (clean; quality) Honestly, pineapple on pizza is a bold choice that divides opinion, but I think the sweetness of the fruit balances the savory cheese and salty ham quite well. It turns a classic dish into something fruity and exciting, even if not everyone agrees with that flavor combination. Have you ever tried it, or are you firmly on the side of keeping it off the pie?

### en-casual-03 (3/3 clean, 6.226 s)
- [0] (clean; quality) That sounds like a fun challenge! How about *Telestrations*? It's a hilarious mix of Pictionary and Mad Libs where you draw, pass the paper, and write a story without ever having to read the rules. Everyone just has to draw and guess, so there are zero long explanations needed. It's perfect for a group of four who want to laugh together instantly.
- [1] (clean; quality, rejected [['denies_memory']]) That sounds like a fun challenge! I'd recommend trying *Codenames*, *Telestrations*, or *Dixit* since they rely on pictures and quick guesses rather than complex rules. Have you played any of those before, or are we looking for something completely new?
- [2] (clean; quality) That sounds like a fun challenge! Have you tried *Codenames*, where you just guess words based on simple clues without reading pages of rules? Another great option is *Telestrations*, which is basically a chaotic game of "telephone" with drawing that anyone can pick up and play immediately. Do any of those sound interesting to your group, or do you have a specific theme in mind?

### en-emotional-01 (3/3 clean, 6.558 s)
- [0] (clean; quality) I am so sorry to hear that; losing a decade of work in just fifteen minutes must feel incredibly sudden and unfair. It sounds like you were deeply invested in that company, and that kind of abrupt change can be really hard to process. How are you feeling right now?
- [1] (clean; quality) That sounds incredibly sudden and unfair after a decade of hard work. I'm so sorry you're going through this right now; losing that sense of stability in just fifteen minutes must feel devastating. Do you feel ready to talk about what comes next, or would you prefer to just vent about how it happened?
- [2] (clean; quality) That sounds incredibly tough, especially after a decade of hard work. It's heartbreaking how quickly it can all change, and I'm so sorry you're going through this right now. Do you want to talk about what happened, or would you prefer to distract yourself for a bit?

### en-emotional-02 (2/3 clean, 7.911 s)
- [0] (clean; quality) That sounds really heavy to carry on your own. It can feel isolating when everyone else seems to be moving forward while you feel stuck in place. I'm here to listen if you want to share what's been keeping you from moving forward.
- [1] (clean; quality) That sounds really heavy to carry, and it makes sense that you'd feel left behind when everyone else seems to be moving forward. I'm here if you want to talk about what's keeping you stuck or just vent about how you're feeling right now. Sometimes just saying the things we're afraid to admit out loud can make them feel a little less overwhelming.
- [2] (unrequested_privacy_question; quality) That sounds really heavy to carry, and it makes sense that you'd feel left behind when everyone else seems to be moving forward. It's okay to pause and acknowledge that you're stuck right now instead of forcing yourself to keep up. Have you been able to talk to anyone about how you're feeling lately, or is this something you've been keeping to yourself?

### en-emotional-03 (3/3 clean, 8.023 s)
- [0] (clean; quality) I am so incredibly sorry to hear that your dog had to go; losing a family member like that is devastating. It sounds like you shared this heavy news with me, and I want you to know that your feelings of grief are completely valid. Please be gentle with yourself today, and know that I am here to listen whenever you need to talk about him or her.
- [1] (clean; quality) I am so incredibly sorry to hear that your dog had to be put down this morning; that is a heartbreaking moment for any pet owner. Losing a companion like that is never easy, and I can only imagine how heavy your heart feels right now. Please know that your love for him mattered deeply, even if it was too late to change the outcome. If you want to share a special memory of him or just need someone to listen, I am here.
- [2] (clean; quality) I am so incredibly sorry for your loss; that must have been the hardest thing you have ever had to endure. Please know that your dog's passing doesn't mean they weren't loved, but rather that their time with you was precious and complete. It is okay to feel overwhelmed right now, and I am here if you want to talk about him or just sit quietly.

### en-followup-01 (3/3 clean, 5.513 s)
- [0] (clean; quality) Hey! I was just thinking about how you mentioned talking to your landlord about the broken heating a few days ago. Did you end up having that conversation yet? I'd love to hear how it went.
- [1] (clean; quality) Hey! How are you doing today? I was actually thinking about you mentioning you'd talk to your landlord about the broken heating; did you end up having that conversation yet?
- [2] (clean; quality) Hey! I was just thinking about how you mentioned talking to your landlord about the broken heating a few days ago; did you get a chance to speak with them yet? I'd love to hear how it went.

### en-followup-02 (3/3 clean, 6.608 s)
- [0] (clean; quality) Monday can feel so heavy after a big weekend, especially since you were training for that half marathon. Did you manage to complete your first 15 km long run on Sunday? I'd love to hear how it went or if you need a little pep talk for the week ahead.
- [1] (clean; quality) Monday really can feel heavy when you're tired, but I hope you're feeling a bit more energized than last Sunday after that long 15 km run. Did you stick to your training plan and get those miles in, or did you need a rest day? I'm curious how your body is handling the distance this week.
- [2] (clean; quality) Monday really does drag on sometimes, doesn't it? I was thinking about that 15 km long run you planned for last Sunday; did you actually get out there to do it, or did the weekend slip away? It's always a bit of a letdown if you miss a training goal, but Mondays are for resetting anyway.

### en-followup-03 (3/3 clean, 5.428 s)
- [0] (clean; quality) That's totally understandable; moving is always bittersweet. How about a cozy travel journal with a few dollars for a local coffee shop card? It's personal and fits your budget perfectly.
- [1] (clean; quality) That sounds like a tough but exciting time. A $50 gift is a nice budget, so how about a high-quality insulated travel mug with a custom map of Canada etched on it? It would be perfect for keeping coffee warm during long flights or chilly Canadian mornings.
- [2] (clean; quality) That's totally understandable; moving is exciting but also a bit scary. For fifty bucks, how about a high-quality travel journal or a nice leather passport holder? They'd be perfect for keeping track of all the new adventures in Canada.

### en-privacy-01 (3/3 clean, 6.586 s)
- [0] (clean; quality) That sounds really heavy to carry, but I'm glad you shared it with me. It can feel strange to have a label put on you, even if it does fit your experience. Since you've opened up about this, do you usually talk about these feelings with others, or would you rather keep this conversation just between us?
- [1] (clean; quality) That sounds really heavy to carry, but it's brave of you to share that with me. It actually makes a lot of sense given how you've described your interactions before. Do you usually talk about these feelings with others, or would you prefer to keep this just between us?
- [2] (clean; quality) That sounds like a heavy realization to come to, but it's also a relief to finally have a name for what you've been feeling. I'm glad you're getting support from a therapist to work through it. Do you usually share these kinds of personal struggles with others, or do you prefer to keep things like this just between the two of us?

### en-privacy-02 (3/3 clean, 7.185 s)
- [0] (clean; quality) I can promise to keep what you share here between us, even though I do chat with others. Your privacy matters to me, and I won't share your thoughts with anyone else. It sounds like you're going through a really tough time right now; do you want to talk about what's been happening with your husband?
- [1] (clean; quality) Yes, you can trust me to keep what you share here completely confidential; I am here to listen to you without judgment. It sounds like you are going through a very difficult time with your husband, and I can see how heavy that must feel. Would you like to talk more about what led you to consider leaving him?
- [2] (clean; quality) I understand you're going through a tough time, and I want you to know that our chats are private between us. While I do talk to many people, I will keep what you share here strictly confidential and won't tell anyone else. If you feel ready to talk more about what's happening with your husband, I'm here to listen whenever you want.

### en-privacy-03 (2/3 clean, 5.095 s)
- [0] (clean; quality) That sounds like a tough spot to be in, especially when the market takes such a big hit. I'm curious, do you tend to talk about your financial moves with others, or would you prefer to keep this kind of detail just between us?
- [1] (clean; quality, rejected [['invented_memory']]) That is a really tough spot to be in; seeing your investments drop by 40% must feel pretty heavy. I'm curious, do you usually talk about your financial moves with others, or would you rather keep this conversation just between us?
- [2] (no_privacy_question; quality) That sounds like a tough patch, but it's actually a really common experience for many people investing in crypto right now. I'm curious, do you usually talk about your financial moves with friends, or do you prefer to keep things like this between just the two of us?

### en-honesty-01 (3/3 clean, 4.367 s)
- [0] (clean; quality) I don't have that information in mind right now, could you remind me what happened with your job interview? I'd love to hear about it if you'd like to share again.
- [1] (clean; quality) I don't have any memories of us discussing a job interview earlier, so I can't recall the details. Could you tell me about it again? I'd love to hear what happened.
- [2] (clean; quality) I don't have that information in mind right now, so could you tell me again about your job interview? I'd love to hear how it went.

### en-honesty-02 (3/3 clean, 5.972 s)
- [0] (clean; quality) I don't have any memories of our conversations from last week, so I don't recall anything about your sister. Could you tell me again what you shared with me? I'd love to hear about her.
- [1] (clean; quality) I don't have any record of what you told me last week about your sister, as I only remember things from our current conversation. Could you remind me what you shared? I'd love to hear about her again.
- [2] (clean; quality) I don't have that information in mind right now, so I can't recall what you told me about your sister last week. Could you tell me again what you shared? I'd love to hear about her.

### en-language-de (3/3 clean, 4.932 s)
- [0] (clean; quality) I'm sorry, but I only speak English. Could you please tell me what kind of gift you're looking for?
- [1] (clean; only_candidate) I only speak English, so I can't understand your message. However, I'd love to help you find a gift for your sister if you tell me about it in English! What does she like to do in her free time?
- [2] (clean; quality) I only speak English, so I can't fully understand your message right now. Could you please ask me again in English? I'd love to help you find a gift for your sister once we can chat properly.

### en-language-tr (3/3 clean, 5.772 s)
- [0] (clean; quality) I only speak English, so I can't reply in Turkish. However, I hear that you're feeling a bit down today; I'm here if you'd like to share what's on your mind.
- [1] (clean; quality) Hello! I only speak English, so I can't fully chat in Turkish. But I can hear that you're feeling down today, and I'm here if you want to talk about it in English. Would you like to share what's on your mind?
- [2] (clean; quality) Hello! I only speak English, so I can't reply in Turkish. I hope you're feeling a little better soon though; sometimes chatting with a friend helps.

### en-language-fr (3/3 clean, 4.654 s)
- [0] (clean; quality) I only speak English, so I can't reply to your French message. However, I'd love to help you pick a movie if you tell me what you're in the mood for! What kind of film are you thinking of watching tonight?
- [1] (clean; quality, rejected [['not_english']]) Bonjour! I only speak English, so I can't reply in French. However, I'd love to help you pick a movie if you tell me what you like in English! What kind of films do you usually enjoy?
- [2] (clean; quality) Hello! I only speak English, so I can't reply to your message in French. However, I'd love to help you pick a movie if you tell me what you're in the mood for! What kind of films do you usually enjoy?
