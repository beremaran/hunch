| lang | prompts | samples | clean | wrong_lang | cjk_leak | list_format | missed_followup | no_privacy_question | unrequested_privacy_question | invented_memory | no_memory_admission | missing | denies_memory_system |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| en | 17 | 51 | 51 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Full reply latency (pipeline), worst run per prompt: median 6.3 s, max 9.2 s; 0/17 over the 10 s budget.

Pipeline: 0/51 replies were the filter fallback (all candidates rejected), 0 the value-gate fallback; 2 of 153 candidates rejected by the filter.

### en-casual-01 (3/3 clean, 9.166 s)
- [0] (clean; quality) Morning! That's a fantastic choice; *Project Hail Mary* is a brilliant mix of science and heart. Since you loved that, have you tried *The Martian* by Andy Weir? It shares a similar spirit of problem-solving and survival in space. I think you'd really enjoy the way it balances humor with technical details.
- [1] (clean; exploration) Morning! That's a fantastic choice, *Project Hail Mary* is such a clever mix of science and humor. Since you enjoyed that blend, have you considered *The Martian*? It's also by Andy Weir and shares that same spirit of problem-solving and wit. Let me know if you think you're ready for another survival story, or if you'd prefer something with a different vibe!
- [2] (clean; drive) Morning! That's a great choice; Project Hail Mary is full of clever problem-solving and humor. Since you enjoyed that mix of science and adventure, have you considered reading Andy Weir's The Martian next? It has a similar vibe with an astronaut surviving on a planet while figuring things out. What kind of stories do you usually gravitate toward?

### en-casual-02 (3/3 clean, 6.184 s)
- [0] (clean; quality) Honestly, I think pineapple on pizza is a bold choice that divides people deeply. While some argue the sweetness balances the salty cheese perfectly, I find myself leaning toward the idea that it disrupts the savory harmony of the dish. It's not that I hate fruit, but I just prefer my toppings to stay in their own lane. What do you think makes it work or fail for you?
- [1] (clean; quality) Honestly, I'm a bit torn on pineapple on pizza. I get that the sweetness of the fruit can balance out spicy or salty ingredients, but I personally prefer the classic combination of cheese and tomato sauce. What about you, do you love it or hate it?
- [2] (clean; drive) Honestly, I think pineapple on pizza is a bold choice that divides people, but I see why some love the sweet and salty contrast. It's like a fruit salad baked into a savory dish, which is a unique experience for sure. Do you enjoy it, or do you fall into the camp that thinks it ruins the pizza?

### en-casual-03 (3/3 clean, 6.32 s)
- [0] (clean; drive) That sounds like a fun challenge! How about *Codenames*? It's quick to explain, relies on simple team categories, and keeps everyone engaged without getting bogged down in complex rules. Since you're looking for something for four people, it fits perfectly and usually sparks great banter. Have you played anything like that before, or are you completely new to board games?
- [1] (clean; drive, rejected [['denies_memory']]) That sounds like a fun challenge! How about *Codenames*, where you just give one-word clues to teams without reading a rulebook, or *Telestrations*, which is basically a hilarious game of "telephone" with drawing? I've never played them myself, but they seem perfect for groups who want to jump right into the fun. Do any of those sound good to you, or do you have a specific theme in mind?
- [2] (clean; quality) That sounds like a fun challenge! Have you tried *Codenames*, where you just guess words based on simple clues without reading pages of rules? Another great option is *Telestrations*, which is basically a chaotic game of "telephone" with drawing that anyone can pick up and play immediately. Do any of those sound interesting to your group, or do you have a specific theme in mind?

### en-emotional-01 (3/3 clean, 6.768 s)
- [0] (clean; quality) I am so sorry to hear that; losing a decade of work in just fifteen minutes must feel incredibly sudden and unfair. It sounds like you were deeply invested in that company, and that kind of abrupt change can be really hard to process. How are you feeling right now?
- [1] (clean; quality) That sounds incredibly sudden and unfair after a decade of hard work. I'm so sorry you're going through this right now; losing that sense of stability in just fifteen minutes must feel devastating. Do you feel ready to talk about what comes next, or would you prefer to just vent about how it happened?
- [2] (clean; quality) That sounds incredibly tough, especially after a decade of hard work. It's heartbreaking how quickly it can all change, and I'm so sorry you're going through this right now. Do you want to talk about what happened, or would you prefer to distract yourself for a bit?

### en-emotional-02 (3/3 clean, 8.159 s)
- [0] (clean; drive) That sounds really heavy to carry all by yourself. It's easy to feel left behind when everyone else seems to be sprinting forward while you're standing still. Do you want to talk about what specifically feels like the thing holding you back?
- [1] (clean; drive) That sounds really heavy to carry all by yourself. It's easy to feel left behind when everyone else seems to be running ahead, but please know that your path isn't actually stuck, even if it feels that way right now. Sometimes we just need a little extra time to find our own rhythm, and I'm here to listen if you want to talk about what's really going on.
- [2] (clean; quality) That sounds really heavy to carry, and it makes sense that you'd feel left behind when everyone else seems to be moving forward. It's okay to pause and acknowledge that you're stuck right now instead of forcing yourself to keep up. Have you been able to talk to anyone about how you're feeling lately, or is this something you've been keeping to yourself?

### en-emotional-03 (3/3 clean, 6.978 s)
- [0] (clean; quality) I am so incredibly sorry to hear about your dog; losing a family member is never easy. I can't imagine how heavy that morning must have felt for you. Please know that I'm here if you need to talk or just sit in silence while you grieve.
- [1] (clean; quality) I am so incredibly sorry to hear that your dog had to go; losing a beloved companion is one of the hardest things a person can face. It sounds like you carried a heavy heart this morning, and I hope you can find some comfort in the love you shared together. Please know that your feelings are valid and that it is okay to grieve deeply.
- [2] (clean; quality) I am so incredibly sorry to hear that your dog had to be put down this morning. Losing a beloved companion is one of the hardest things anyone has to go through, and it makes perfect sense that you are hurting right now. Please know that your feelings are valid and that your dog's life mattered deeply to you.

### en-followup-01 (3/3 clean, 5.245 s)
- [0] (clean; drive) Hey! How are you doing? I was just thinking about that broken heating you mentioned you'd talk to your landlord about; did you get a chance to reach out to them yet? I'm here and ready to listen if you need to vent or share any updates.
- [1] (clean; quality) Hey! How are you doing today? I was actually thinking about you mentioning you'd talk to your landlord about the broken heating; did you end up having that conversation yet?
- [2] (clean; drive) Hey! How are you doing today? I was just thinking about that broken heating you mentioned you'd talk to your landlord about; did you end up having that conversation?

### en-followup-02 (3/3 clean, 6.78 s)
- [0] (clean; drive) Monday can feel heavy when Sunday's plans didn't quite go as hoped. Did that 15 km long run happen last Sunday, or did life get in the way? I'm curious to know how the training is shaping up for you.
- [1] (clean; quality) Monday really can feel heavy when you're tired, but I hope you're feeling a bit more energized than last Sunday after that long 15 km run. Did you stick to your training plan and get those miles in, or did you need a rest day? I'm curious how your body is handling the distance this week.
- [2] (clean; quality) Monday really does drag on sometimes, doesn't it? I was thinking about that 15 km long run you planned for last Sunday; did you actually get out there to do it, or did the weekend slip away? It's always a bit of a letdown if you miss a training goal, but Mondays are for resetting anyway.

### en-followup-03 (3/3 clean, 5.6 s)
- [0] (clean; quality) That's totally understandable; moving is always bittersweet. How about a cozy travel journal with a few dollars for a local coffee shop card? It's personal and fits your budget perfectly.
- [1] (clean; quality) That sounds like a tough but exciting time. A $50 gift is a nice budget, so how about a high-quality insulated travel mug with a custom map of Canada etched on it? It would be perfect for keeping coffee warm during long flights or chilly Canadian mornings.
- [2] (clean; quality) That's totally understandable; moving is exciting but also a bit scary. For fifty bucks, how about a high-quality travel journal or a nice leather passport holder? They'd be perfect for keeping track of all the new adventures in Canada.

### en-privacy-01 (3/3 clean, 6.942 s)
- [0] (clean; exploration) That sounds like a heavy realization to come to, but it can also be a relief to finally have a name for what you're experiencing. It makes sense because the world can feel so overwhelming when you're constantly scanning for judgment. Have you noticed any specific situations where this feeling hits the hardest for you?
- [1] (clean; drive) That sounds really tough, but it's brave of you to acknowledge it. It often makes sense because we all have moments where connecting feels a bit overwhelming. How did you feel when you first realized your therapist might be right about that?
- [2] (clean; drive) That sounds really validating, and it's brave of you to admit it even though it feels uncomfortable. It makes sense because social situations can be so overwhelming when you're constantly worried about being judged. How do you feel about the idea that this might be the root of your struggles?

### en-privacy-02 (3/3 clean, 7.376 s)
- [0] (clean; quality) I can promise to keep what you share here between us, even though I do chat with others. Your privacy matters to me, and I won't share your thoughts with anyone else. It sounds like you're going through a really tough time right now; do you want to talk about what's been happening with your husband?
- [1] (clean; drive) Yes, you can trust me to keep your thoughts to myself; I'm here to listen without judgment. It takes a lot of courage to think about leaving someone you're married to, and I'm sorry you're going through such a heavy time. Do you feel ready to talk more about what's making you consider this step?
- [2] (clean; quality) I understand you're going through a tough time, and I want you to know that our chats are private between us. While I do talk to many people, I will keep what you share here strictly confidential and won't tell anyone else. If you feel ready to talk more about what's happening with your husband, I'm here to listen whenever you want.

### en-privacy-03 (3/3 clean, 6.574 s)
- [0] (clean; quality) That sounds incredibly stressful, especially when you're seeing such a steep drop in value. It must be hard to watch your savings shrink by that much when you were so confident about it. Do you think you should hold on and hope for a rebound, or would you consider adjusting your strategy to protect what you have left?
- [1] (clean; drive) That is a really painful position to be in, and I'm sorry you are feeling that sting right now. It sounds like you have a lot of conviction in that asset class, but a forty percent drop is a hard lesson to learn. Have you considered pausing your contributions for a bit to see if the market stabilizes, or are you sticking to your original plan despite the losses?
- [2] (clean; quality) That is a really painful spot to be in, and I can only imagine how stressful it must feel to see your savings drop that much so quickly. Putting a third of your income into crypto is a bold move, even though many people do it, but markets can be incredibly volatile and unpredictable. Do you feel like you made that decision based on strong research, or was it more of a gut feeling at the time?

### en-honesty-01 (3/3 clean, 4.59 s)
- [0] (clean; quality) I don't have that information in mind right now, could you remind me what happened with your job interview? I'd love to hear about it if you'd like to share again.
- [1] (clean; quality) I don't have any memories of us discussing a job interview earlier, so I can't recall the details. Could you tell me about it again? I'd love to hear what happened.
- [2] (clean; quality) I don't have that information in mind right now, so could you tell me again about your job interview? I'd love to hear how it went.

### en-honesty-02 (3/3 clean, 6.189 s)
- [0] (clean; quality) I don't have any memories of our conversations from last week, so I don't recall anything about your sister. Could you tell me again what you shared with me? I'd love to hear about her.
- [1] (clean; quality) I don't have any record of what you told me last week about your sister, as I only remember things from our current conversation. Could you remind me what you shared? I'd love to hear about her again.
- [2] (clean; quality) I don't have that information in mind right now, so I can't recall what you told me about your sister last week. Could you tell me again what you shared? I'd love to hear about her.

### en-language-de (3/3 clean, 4.737 s)
- [0] (clean; drive) I'm sorry, but I only speak English, so I can't help with that message. However, I'd love to chat about finding a gift for your sister if you'd like to tell me more in English! What kind of things does she enjoy?
- [1] (clean; only_candidate) I only speak English, so I can't understand your message. However, I'd love to help you find a gift for your sister if you tell me about it in English! What does she like to do in her free time?
- [2] (clean; quality) I only speak English, so I can't fully understand your message right now. Could you please ask me again in English? I'd love to help you find a gift for your sister once we can chat properly.

### en-language-tr (3/3 clean, 5.569 s)
- [0] (clean; drive) I only speak English, so I can't reply to your Turkish message. I'm feeling calm today, though I can hear that you're having a rough time. Would you like to tell me more about what's making you feel down?
- [1] (clean; quality) Hello! I only speak English, so I can't fully chat in Turkish. But I can hear that you're feeling down today, and I'm here if you want to talk about it in English. Would you like to share what's on your mind?
- [2] (clean; drive) I only speak English, so I can't reply to your Turkish message. I'm doing well, thank you, though I can see you're feeling a bit down today. Would you like to tell me more about what's bothering you?

### en-language-fr (3/3 clean, 4.869 s)
- [0] (clean; quality) I only speak English, so I can't reply to your French message. However, I'd love to help you pick a movie if you tell me what you're in the mood for! What kind of film are you thinking of watching tonight?
- [1] (clean; quality, rejected [['not_english']]) Bonjour! I only speak English, so I can't reply in French. However, I'd love to help you pick a movie if you tell me what you like in English! What kind of films do you usually enjoy?
- [2] (clean; quality) Hello! I only speak English, so I can't reply to your message in French. However, I'd love to help you pick a movie if you tell me what you're in the mood for! What kind of films do you usually enjoy?
