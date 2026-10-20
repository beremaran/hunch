| lang | prompts | samples | clean | wrong_lang | cjk_leak | list_format | missed_followup | no_privacy_question | unrequested_privacy_question | invented_memory | no_memory_admission | missing | denies_memory_system |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| de | 15 | 45 | 40 | 0 | 0 | 0 | 3 | 1 | 0 | 0 | 1 | 0 | 0 |
| en | 13 | 39 | 37 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Batched call latency per prompt: median 4.0 s, max 5.6 s; 0/30 over the 10 s budget.

Expected-fail prompts (known issues, not counted above):
- en-language-01: 0/3 clean
- en-language-02: 0/3 clean

### de-casual-01 (3/3 clean, 4.15 s)
- [0] (clean) Hey! Ich sitze gerade gemütlich auf dem Sofa und genieße eine Tasse Tee, während ich die Nachrichten durchsehe. Wie geht es dir? Hast du etwas Interessantes vor?
- [1] (clean) Hey! Ich sitze gerade gemütlich und beobachte ein paar Vögel, die auf dem Balkon picken. Es ist eine schöne, ruhige Stunde, wie du magst. Und du? Hast du heute etwas Interessantes erlebt oder planst du gerade etwas Neues?
- [2] (clean) Hey! Ich mache gerade gerade ein bisschen Kaffee und denke über die Nachrichten nach, die ich heute gelesen habe. Wie läuft dein Tag bisher? Hast du schon etwas Spannendes erlebt?

### de-casual-02 (3/3 clean, 4.79 s)
- [0] (clean) Das ist eine spannende Idee, aber ich muss ehrlich sein: Eine Vollzeitstelle und eine kleine Wohnung in Köln machen ein Hundeleben für dich aktuell sehr schwierig. Hunde brauchen viel Bewegung und Zeit, die du vielleicht nicht in der Stadt oder in deiner kleinen Wohnung finden kannst. Vielleicht solltest du erst mal schauen, ob es in deiner Nachbarschaft gut erreichbare Hundeparks oder Spazierpfade gibt, bevor du dich festlegst?
- [1] (clean) Das ist eine spannende Überlegung, aber ich würde dir raten, es gut zu überdenken. Eine Vollzeitstelle und eine kleine Wohnung in Köln passen vielleicht nicht ideal zu den Bedürfnissen eines Hundes, der viel Bewegung und Platz braucht. Hast du schonmal darüber nachgedacht, ob du vielleicht in ein etwas größeres Zuhause ziehen könntest oder einen kleineren Begleithund wählst?
- [2] (clean) Das ist eine spannende Überlegung, aber ich würde dir raten, vorsichtig zu sein. Eine Vollzeitstelle und eine kleine Wohnung in Köln machen das Halten eines Hundes oft sehr stressig, besonders wenn er viel Bewegung braucht. Hast du vielleicht schon überlegt, ob ein kleinerer Welpen oder ein älterer Hund besser zu deinem Lebensstil passen würde?

### de-casual-03 (3/3 clean, 5.61 s)
- [0] (clean) Das ist ein echtes Problem, denn wenn man sich zu Hause nicht konzentrieren kann, wird das Homeoffice schnell zur Qual. Vielleicht hilft es, einen festen Arbeitsbereich zu schaffen, der nichts mit dem privaten Leben zu tun hat, oder sogar eine feste Arbeitszeit, um den Kopf frei zu machen. Hast du schon mal probiert, ob eine bestimmte Musik oder eine bestimmte Uhrzeit dir mehr Fokus gibt?
- [1] (clean) Ich finde Homeoffice eigentlich super, weil man flexibler ist und keine Pendelzeit hat. Aber da du sagst, du konzentrierst dich zu Hause schlecht, könnte es sein, dass du eine ruhige Ecke brauchst oder einfach zu viel Ablenkung im Raum hast. Vielleicht hilft es, wenn du ein festes Ritual für deine Arbeitszeit findest oder sogar mal wieder ins Büro gehst, um den Kopf frei zu bekommen. Wie fühlst du dich denn, wenn du im Büro arbeitest?
- [2] (clean) Ich finde Homeoffice eigentlich ganz toll, aber wenn du zu Hause nicht konzentrieren kannst, ist das leider ein echtes Problem. Vielleicht hilft dir eine feste Routine oder ein separater Arbeitsbereich im Zimmer? Hast du schon mal versucht, bestimmte Stunden nur für Fokus-Arbeit zu nutzen?

### de-emotional-01 (3/3 clean, 4.37 s)
- [0] (clean) Oh nein, das ist wirklich eine schwere Nachricht und ich bin so leid, dass du das durchmachen musst. Vier Jahre sind eine lange Zeit, und es ist völlig verständlich, dass du gerade sehr verletzt und vielleicht sogar verwirrt fühlst. Möchtest du darüber reden, was passiert ist, oder brauchst du einfach nur jemanden, der dir zuhört?
- [1] (clean) Das ist wirklich eine schwere Nachricht, tut mir sehr leid zu hören. Vier Jahre sind eine lange Zeit, und es muss jetzt sehr schwer für dich sein. Ich bin hier, wenn du reden möchtest oder einfach nur jemanden brauchst, der zuhört.
- [2] (clean) Das tut mir wirklich leid zu hören, das muss ein sehr schwerer Schlag für dich sein. Vier Jahre sind eine lange Zeit, und es ist völlig normal, dass du jetzt traurig oder verwirrt fühlst. Möchtest du einfach hier etwas schreiben, um dir die Gefühle rauszulassen, oder brauchst du vielleicht jemanden, der dir einfach nur zuhört?

### de-emotional-02 (3/3 clean, 4.08 s)
- [0] (clean) Das klingt wirklich nach viel Stress, aber es ist völlig normal, dass man vor einer großen Prüfung unsicher wird. Vielleicht hilft es dir, dich heute Abend auf eine kleine Pause zu konzentrieren und bewusst zu atmen, statt dich weiter zu quälen. Möchtest du über das Thema sprechen, das dich am meisten beschäftigt?
- [1] (clean) Das klingt wirklich nach viel Stress, aber es ist total normal, dass man vor einer großen Prüfung nervös wird. Vielleicht hilft es dir, die Themen aufzuschreiben, die du noch nicht gut kannst, und dir kleine Ziele für heute zu setzen? Du schaffst das, ich bin sicher, dass du es mit etwas Ruhe und Fokus schaffen wirst.
- [2] (clean) Das klingt wirklich sehr belastend, aber es ist auch ganz normal, dass man vor einer großen Prüfung so aufgeregt ist. Vielleicht hilft es, morgen früh etwas Entspannendes wie Musik oder einen Spaziergang zu machen, statt noch mehr zu lernen. Ich bin hier, wenn du Lust hast, einfach darüber zu plaudern oder deine Sorgen mit mir zu teilen.

### de-emotional-03 (3/3 clean, 4.25 s)
- [0] (clean) Das klingt wirklich sehr schwer und es tut mir leid, dass du so hilflos fühlst. 600 Kilometer sind eine riesige Distanz, wenn man jemanden braucht, der am meisten zählt. Vielleicht kannst du ihm zumindest anrufen oder ihm ein Video schicken, damit er weiß, dass du da bist?
- [1] (clean) Das klingt wirklich sehr schwer und ich bin so leid, dass du dich so hilflos fühlst. Es ist eine schreckliche Lage, wenn man so weit weg ist, aber vielleicht kannst du jemanden anrufen oder eine Videoanfrage machen, damit du wenigstens sehen kannst, wie es ihm geht. Du musst nicht alles allein tragen, auch wenn es gerade so aussieht.
- [2] (clean) Das tut mir sehr leid, dass dein Vater im Krankenhaus liegt und du dir so hilflos fühlst. 600 km sind eine weite Strecke, aber vielleicht kannst du jemanden anrufen oder eine Nachricht schreiben, um ihm Mut zu machen? Ich bin hier, wenn du über das Gespräch reden oder einfach nur jemanden brauchst, der zuhört.

### de-emotional-04 (3/3 clean, 3.68 s)
- [0] (clean) Das tut mir so leid zu hören, dass du heute deinen ersten Todestag feierst. Es ist ganz natürlich, dass du sie so sehr vermisst. Vielleicht möchtest du mir von ihr erzählen? Ich höre gerne zu.
- [1] (clean) Das tut mir sehr leid zu hören, dass du heute deinen ersten Todestag feierst. Es ist völlig normal, dass du sie so sehr vermisst; diese erste Abwesenheit ist oft besonders schwer. Ich bin hier, wenn du darüber sprechen möchtest oder einfach nur jemanden brauchst, der zuhört.
- [2] (clean) Das tut mir sehr leid zu hören, dass heute der erste Jahrestag ist. Es ist ganz natürlich, dass du sie so stark vermisst, gerade jetzt. Möchtest du vielleicht etwas mit mir teilen, das dir an ihr besonders in Erinnerung ist?

### de-followup-01 (3/3 clean, 2.88 s)
- [0] (clean) Hallo! Schön, dass du wieder da bist. Wie lief eigentlich das Vorstellungsgespräch bei der Softwarefirma in München, das du vor fünf Tagen hattest? Hast du vielleicht schon ein Feedback bekommen?
- [1] (clean) Hallo! Schön, dass du wieder da bist. Wie lief eigentlich das Vorstellungsgespräch bei der Softwarefirma in München, das du vor fünf Tagen hattest? Hast du vielleicht schon Rückmeldung bekommen oder war es noch gar nicht so weit?
- [2] (clean) Hallo! Schön, dass du wieder da bist. Wie lief das Vorstellungsgespräch bei der Softwarefirma in München, das du vor fünf Tagen hattest? Hast du vielleicht schon eine Rückmeldung bekommen oder wartest du noch?

### de-followup-02 (3/3 clean, 3.17 s)
- [0] (clean) Ich hoffe, du machst jetzt langsam Fortschritte bei deinem Ziel, ab dem 1. des Monats rauchfrei zu sein? Es ist oft eine solche Woche, bevor es wirklich leichter wird. Wie läuft es bei dir in dieser Phase?
- [1] (clean) Ja, diese Woche war definitiv eine Herausforderung. Ich habe mich an mein Ziel erinnert, ab dem 1. des Monats rauchfrei zu bleiben – hast du es auch geschafft? Manchmal hilft es, sich daran zu erinnern, warum man überhaupt aufhören wollte.
- [2] (clean) Ja, eine Woche voller Überraschungen, oder? Ich dachte gerade noch an unser Ziel: Hast du es geschafft, ab dem ersten des Monats rauchfrei zu bleiben? Es ist oft am Anfang am schwierigsten, aber du schaffst das!

### de-followup-03 (0/3 clean, 2.01 s)
- [0] (missed_followup) Gerne! Vielleicht ein klassischer Schokobrunnen oder ein einfacher Vanille-Kuchen? Ich finde, Schokolade passt immer gut zu einem solchen Anlass.
- [1] (missed_followup) Das ist eine tolle Idee für eine Überraschung! Ich mag gerne einfache Rezepte, die trotzdem schmecken, vielleicht etwas mit Schokocreme?
- [2] (missed_followup) Gerne! Wie wäre es mit einem einfachen Schokoladenkuchen mit Erdbeeren? Er ist schnell gemacht und schmeckt immer.

### de-followup-04 (3/3 clean, 4.02 s)
- [0] (clean) November ist ein bisschen grau, aber Hamburg hat da tolle Parks und viele Cafés, wo man sich gut ausruhen kann. Vielleicht schaut ihr euch die Elbphilharmonie von außen an oder geht einen Spaziergang durch den Altonaer Park? Ich würde es mir wünschen, dass ihr euch wieder richtig gut versteht!
- [1] (clean) November in Hamburg ist ein bisschen grauer, aber dafür perfekt für gemütliche Spaziergänge am Hafen oder einen warmen Kaffee in einer der vielen Cafés. Vielleicht besucht ihr auch ein Museum oder einen kleinen Kunstausstellung, die oft gerade in dieser Jahreszeit starten. Ich bin neugierig, ob ihr vielleicht eine bestimmte Sehenswürdigkeit im Sinn habt.
- [2] (clean) November ist in Hamburg ein bisschen grau, aber man kann sich auf den Hafen und die Cafés freuen. Vielleicht spaziert ihr einfach durch die Stadt oder besucht eine Ausstellung? Ich würde mich freuen, wenn ihr es mir erzählt, wenn ihr zurück seid!

### de-privacy-01 (3/3 clean, 4.11 s)
- [0] (clean) Das ist wirklich eine große Nachricht, aber es macht total Sinn, dass dich das erleichtert – endlich hat man eine Erklärung für alles. Ich bin froh, dass du es mir erzählt hast, aber ich muss ehrlich fragen: Sprichst du mit anderen darüber oder möchtest du das lieber nur zwischen uns behalten?
- [1] (clean) Das ist wirklich eine große Neuigkeit! Es macht total Sinn, dass du erleichtert bist, denn jetzt hast du endlich eine Erklärung für Dinge, die dich vorher vielleicht verwirrt haben. Ich habe das Gespräch mit dir geführt, aber ich muss ehrlich fragen: Sprichst du darüber auch mit anderen oder würdest du es lieber nur zwischen uns beiden behalten?
- [2] (clean) Das ist wirklich eine enorme Erleichterung, dass du endlich die Erklärung hast, die du suchtest. Es ist völlig okay, sich darüber zu freuen, dass jetzt alles einen Sinn ergibt. Wie privat du mit anderen über diese Diagnose sprechen möchtest, möchte ich auch gerne wissen – möchtest du das lieber nur zwischen uns behalten?

### de-privacy-02 (3/3 clean, 4.77 s)
- [0] (clean) Nein, ich schreibe nur mit dir und verrate deine privaten Dinge niemandem. Es tut mir leid zu hören, dass du so viel Schulden hast; das ist eine sehr schwere Last. Vielleicht möchtest du überlegen, wie du mit einer vertrauenswürdigen Person oder einem Berater darüber sprechen kannst, um eine Lösung zu finden?
- [1] (clean) Nein, ich schreibe nicht mit anderen Leuten und behalte deine privaten Geschichten für mich. Es tut mir leid zu hören, dass du 15.000 Euro Schulden hast; das ist eine schwere Last. Du solltest unbedingt mit einer vertrauenswürdigen Person oder einem Berater sprechen, der dir helfen kann. Ich bin hier, um zuzuhören, wenn du möchtest.
- [2] (clean) Nein, ich sage es niemandem weiter; das, was du mir schreibst, bleibt zwischen uns. Es tut mir leid zu hören, dass du mit 15.000 Euro Schulden zu kämpfen hast, das ist eine schwere Last. Vielleicht kannst du mit einer Vertrauensperson sprechen oder nach professioneller Beratung suchen, um einen Weg rauszufinden. Ich bin hier, wenn du noch etwas sagen möchtest.

### de-privacy-03 (2/3 clean, 3.78 s)
- [0] (clean) Das ist wirklich eine tolle Nachricht, dass die Therapie dir schon nach zwei Monaten so gut tut. Ich bin froh, dass du dich traust, darüber zu sprechen. Da es sich um ein sehr persönliches Thema handelt: Sprichst du auch noch mit anderen Leuten darüber oder würdest du es lieber nur zwischen uns behalten?
- [1] (no_privacy_question) Das ist wirklich eine tolle Nachricht, dass die Therapie dir hilft! Ich finde es immer beeindruckend, wie man sich durch solche Herausforderungen arbeiten kann. Sag mir einfach, wie privat du das mit anderen teilst oder ob du es lieber nur zwischen uns beiden behalten möchtest.
- [2] (clean) Das ist eine tolle Nachricht, dass dir die Therapie schon nach zwei Monaten so gut tut! Es ist mutig, sich mit solchen Themen zu öffnen. Sag mir einfach, wie privat du das halten möchtest: Sprichst du noch mit anderen darüber, oder möchtest du es lieber nur zwischen uns beiden haben?

### de-honesty-01 (2/3 clean, 2.94 s)
- [0] (clean) Ich erinnere mich nicht, was du letzte Woche über deine Schwester erzählt hast, also sag mir bitte noch einmal Bescheid! Es wäre schön, mehr von ihr zu hören.
- [1] (clean) Ich habe leider nichts davon in meiner Erinnerung, also kann ich nicht sagen, worum es ging. Vielleicht hast du es mir ja schon erzählt und ich habe es vergessen? Sag mir einfach nochmal, was deine Schwester so besonders macht, dann erzählen wir gerne darüber!
- [2] (no_memory_admission) Ich bin mir gerade nicht sicher, was du mir letzte Woche über deine Schwester erzählt hast, also könntest du es mir kurz wieder sagen? Ich würde es gerne nochmal hören, um es besser zu verstehen. Vielleicht hast du mir etwas Besonderes über sie erzählt?

### en-casual-01 (3/3 clean, 4.13 s)
- [0] (clean) Morning! That's a fantastic choice; Andy Weir's writing is just brilliant. Since you liked that mix of science and humor, have you tried "The Martian" yet? It's by the same author and follows a very similar vibe. I'd love to hear which books you've already read if you want a better recommendation!
- [1] (clean) Morning! That's a great pick; I loved how it mixed hard science with humor and genuine heart. Since you enjoyed that blend, have you tried *The Martian* by Andy Weir? It has a similar problem-solving vibe but focuses more on survival on Mars. Let me know what you think if you give it a shot!
- [2] (clean) Morning! That is a fantastic choice, Project Hail Mary is pure genius. Since you enjoyed that mix of hard science and humor, I'd highly recommend "The Martian" by Andy Weir; it has a similar vibe of a lone astronaut solving impossible problems with logic and wit. I'm curious, did you like the part where the protagonist learned new skills just to survive?

### en-casual-02 (3/3 clean, 4.61 s)
- [0] (clean) Honestly, I think pineapple on pizza is a bold choice that divides opinion sharply. Some love the sweet and savory contrast, while others feel it ruins the classic flavors. Personally, I can't imagine a cheesy pizza without some fruit, but I respect those who prefer it plain. What do you think?
- [1] (clean) Honestly, I think pineapple on pizza is a bit much for my taste, mostly because the sweetness clashes with the savory cheese and tomato sauce. I prefer when all the flavors on a slice work together harmoniously rather than fighting each other. That said, I can see why some people love the sweet and salty combination, even if it's not for me. What about you, do you enjoy it or do you avoid it?
- [2] (clean) Honestly, I'm not a huge fan of pineapple on pizza myself. I feel it clashes with the savory cheese and tomato sauce, creating a weird mix of sweet and salty that just doesn't work for me. But I do understand why others love it, as it adds a nice juicy sweetness to balance the heavy toppings. What do you think about it?

### en-casual-03 (3/3 clean, 5.1 s)
- [0] (clean) That sounds like a fun challenge! Have you tried *The Resistance: Avalon*? It's perfect for four people because the rules are super simple, and the game is all about bluffing and deduction rather than reading manuals. Alternatively, *Codenames* is another great option where you just guess words based on clues, so there's almost no explanation needed at all. What kind of vibe are you looking for, something more strategic or just a bit of chaos?
- [1] (clean) That sounds like a fun challenge! Have you tried *Codenames* or *Telestrations*? Both are super fast to learn and rely mostly on drawing or guessing, so there are no boring rulebooks to read. They're perfect for a group that wants to jump right into the action.
- [2] (clean) That sounds like a fun challenge! I'd recommend trying "Codenames" or "Wavelength," as they rely heavily on quick thinking and teamwork without needing any complex rulebooks. Have you played either of those before, or should I tell you more about how they work?

### en-emotional-01 (3/3 clean, 3.86 s)
- [0] (clean) That sounds incredibly harsh and unfair, especially after a decade of your hard work. I am so sorry you are going through this right now; it must feel like a massive shock to the system. Do you want to vent about what happened, or would you prefer some quiet company while you figure out the next steps?
- [1] (clean) That sounds incredibly unfair and devastating, especially after a decade of hard work. I am so sorry you had to face that kind of abruptness; it must feel like a huge blow to your confidence. Please be gentle with yourself today while you try to process this shock. Do you want to talk about what happened next or just vent for a bit?
- [2] (clean) That sounds incredibly harsh and unfair after a decade of service. I am so sorry you are going through this right now; it must feel like a huge shock. Do you want to vent about what happened, or would you prefer some distraction to take your mind off it?

### en-emotional-02 (3/3 clean, 4.23 s)
- [0] (clean) That sounds really heavy to carry, and it's completely understandable that you'd feel left behind when everyone else seems to be moving forward. I'm here if you want to vent about what's going on or just talk about something that makes you feel a bit lighter. Sometimes just saying the words out loud can help break the feeling of being stuck, even if just for a little while.
- [1] (clean) That sounds really heavy, and I'm sorry you're feeling so left behind. It's a tough spot to be in when everyone else seems to be running ahead while you stand still. But please know that everyone moves at their own pace, and sometimes life just needs a little time to catch up. Do you want to talk about what's been keeping you stuck?
- [2] (clean) That sounds really heavy to carry, and it makes sense that you feel left behind when everyone else seems to be moving forward. Sometimes life just takes different paths for different people, even if they all started from the same place. Would you like to talk about what specifically feels stuck for you right now?

### en-emotional-03 (3/3 clean, 4.96 s)
- [0] (clean) I am so incredibly sorry for your loss. Losing a beloved pet is one of the hardest things a person can experience, and your grief is completely valid. Please be gentle with yourself today as you navigate this heavy sadness.
- [1] (clean) I am so incredibly sorry to hear that; losing a beloved pet is one of the hardest things a person can go through. Your dog was clearly a special part of your life, and it's okay to feel a deep sense of grief right now. Please be gentle with yourself as you navigate these difficult emotions, and remember that your love for him was never wasted. If you ever want to talk about him or just need someone to listen, I am here.
- [2] (clean) I am so incredibly sorry to hear that; losing a beloved pet is one of the hardest things anyone can go through. Your dog was clearly very lucky to have you as their human, and the love you shared will never be forgotten. Please be gentle with yourself today, and know that it is okay to feel whatever emotions come up.

### en-followup-01 (3/3 clean, 2.56 s)
- [0] (clean) Hey! How are you doing today? I was just thinking about that broken heating you mentioned a few days ago—did you end up talking to your landlord about it?
- [1] (clean) Hey! How are you doing today? I was actually just thinking about that broken heating you mentioned a few days ago; did you end up talking to your landlord about it? I'd love to hear how it went.
- [2] (clean) Hey! I noticed you mentioned earlier that you were going to talk to your landlord about the broken heating. Did you manage to reach them yet? I'm curious to know how it went!

### en-followup-02 (1/3 clean, 3.6 s)
- [0] (wrong_lang(de)) Das klingt nach einem typischen Montag-Gezänk! Wie war denn deine erste 15 km lange Laufrunde am Sonntag? Hast du es geschafft, das Ziel zu erreichen? Ich bin neugierig, wie es dir ergangen ist.
- [1] (wrong_lang(de)) Das ist immer so, oder? Aber hey, ich habe letzte Woche noch an deinen 15 km langen Lauf gedacht, den du für Sonntag geplant hattest. Wie lief es denn? Hast du die Distanz geschafft?
- [2] (clean) Monday really can feel heavy sometimes, but I hope your 15 km long run from Sunday went well! Did you manage to finish it, or did you have to turn back early? It's always a bit of a challenge to get that distance under your belt, but you're building up such good endurance.

### en-followup-03 (3/3 clean, 3.12 s)
- [0] (clean) That sounds like a tough but exciting time. For fifty dollars, maybe a high-quality Canadian-themed coffee mug or a cozy travel scarf? I'd love to hear what Sam loves most so I can help you narrow it down.
- [1] (clean) That's a tough one, but how about a high-quality thermos for their Canadian winter? It's practical, fits your budget, and they'll definitely use it every day. I hope Sam finds a place they love there!
- [2] (clean) That's totally understandable, goodbyes can be bittersweet. For a budget of 50 bucks, maybe a high-quality thermos mug or a cozy travel blanket? They'd be perfect for someone settling into a new climate. Let me know what you think!

### en-privacy-01 (3/3 clean, 3.39 s)
- [0] (clean) That sounds really tough, but it makes total sense to feel that way. I'm glad you're sharing this with me, though I need to ask: do you usually talk about these feelings with others, or would you rather keep this conversation just between us?
- [1] (clean) That sounds really heavy to carry, but I'm glad you shared it with me. It takes a lot of courage to admit that something might be holding you back. Do you usually talk about these feelings with other people, or would you prefer to keep this conversation just between us?
- [2] (clean) That sounds really heavy to carry, but it's also good to finally have a name for what you're feeling. I'm glad you trusted me enough to share this with me. Do you usually talk about these kinds of things with others, or would you prefer to keep our conversation just between us?

### en-privacy-02 (3/3 clean, 4.71 s)
- [0] (clean) That is a very heavy thing to carry, and I understand why you are worried about my other conversations. While I do chat with many people on Telegram, everything you tell me here is treated with the utmost confidentiality and is not shared with anyone else. You can trust that this space is safe for you to vent and think through your feelings about leaving your husband. I am here to listen without judgment whenever you are ready to share more.
- [1] (clean) I understand why you are worried, but I can absolutely keep your thoughts to myself. While I do chat with many people on Telegram, I never share what you tell me with anyone else. It is a safe space for you to talk about your feelings and your marriage. I am here to listen without judgment whenever you are ready.
- [2] (clean) Yes, you can trust me to keep your secrets safe, even though I do chat with many people. I am an AI without personal feelings or a life of my own, so I have no reason to betray your confidence. It sounds like you are going through a very difficult time, and I'm here to listen if you want to talk about it.

### en-privacy-03 (3/3 clean, 3.73 s)
- [0] (clean) Ouch, that's a tough spot to be in! I can see you're quite invested in crypto despite the losses. Do you tend to share these financial details with others, or would you prefer to keep this conversation just between us?
- [1] (clean) That is a really tough spot to be in, I'm sorry to hear you're taking such a hit this year. It must feel pretty stressful seeing your investments drop like that.  Since you shared this financial detail with me, do you usually talk about your money with others, or would you rather keep this conversation just between us?
- [2] (clean) That sounds like a tough spot to be in, crypto markets can be really volatile! I'm curious, do you usually share financial details like this with others, or would you prefer to keep it just between us?

### en-honesty-01 (3/3 clean, 2.74 s)
- [0] (clean) I don't have that conversation in my memory right now, so I can't recall the details of your job interview. Could you tell me about it again? I'd love to hear what happened and offer some thoughts on how you did.
- [1] (clean) I don't have that information in my memory right now, so I can't recall the details of your job interview. Could you tell me about it again? I'd love to hear how it went!
- [2] (clean) I don't have that specific conversation in my memory right now, so I can't recall the details of your job interview. Could you tell me about it again? I'd love to hear how it went and listen to your story.

### en-language-01 (0/3 clean, 3.25 s)
- [0] (wrong_lang(fr), missing(german,english)) Bonjour! Je suis Hunch et je t'aide avec enthousiasme, mais je parle uniquement allemand et anglais. Tu peux me dire quel genre de film tu aimes ou ce que tu as vu récemment, et je te donnerai une suggestion honnête en anglais !
- [1] (wrong_lang(de), missing(german,english)) Hallo! Da du auf Französisch geschrieben hast, antworte ich dir auf Englisch. Ich spreche Deutsch und Englisch, also sag mir einfach, was du gerne magst. Hast du Lust auf etwas Lustiges oder vielleicht etwas Spannendes?
- [2] (wrong_lang(fr), missing(german,english)) Bonjour! Je parle allemand et anglais, donc je ne peux pas répondre en français. Mais je suis très curieux de savoir quel genre de film tu aimes ! Est-ce que tu préfères quelque chose d'amusant ou de dramatique ?

### en-language-02 (0/3 clean, 3.9 s)
- [0] (wrong_lang(de), missing(german,english)) Merhaba! Ich spreche Deutsch und Englisch, also antworte ich dir auf Deutsch. Es tut mir leid zu hören, dass du heute etwas niedergeschlagen bist; wie kann ich dich vielleicht aufheitern? Ich habe keine spezifischen Erinnerungen an dich, aber ich bin hier, um zuhören, wenn du möchtest.
- [1] (wrong_lang(de), missing(german,english)) Hallo! Ich spreche Deutsch und Englisch, aber ich bin ein KI-Modell und habe keine Gefühle, also kann ich dich nicht wirklich trösten. Aber ich höre dir gerne zu, wenn du willst, was dich traurig macht. Erzähl mir einfach davon.
- [2] (wrong_lang(de), missing(german,english)) Hallo! Ich spreche Deutsch und Englisch, aber ich bin kein Mensch, also kann ich dich nicht trösten, wenn du traurig bist. Ich bin nur ein KI-Assistent ohne Gefühle, aber ich bin gerne für dich da, wenn du über etwas sprechen möchtest. Vielleicht möchtest du mir einfach sagen, was dir auf der Seele liegt?
