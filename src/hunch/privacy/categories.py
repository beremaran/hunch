"""Sensitive categories for the privacy module (Phase 5).

A message is "in" a category when the user shares PERSONAL information of that kind about
themselves or someone close to them. The same word used impersonally is not enough: "my bank's app
is down", "a documentary about depression", "the court near my flat", "sick of this weather",
"politics on tv is exhausting" are all outside every category. Two halves, ORed in
`CategoryDetector.detect`:

- keywords: regex fragments with personal framings ("my salary", "i owe 500 euros", "can't make
  rent", "my therapist", "diagnosed with", "got fired", "my boss ... yelled"). Precision matters
  more than recall; the fragments avoid bare nouns that are mostly impersonal.
- embeddings: max cosine similarity to the category's first-person prototype sentences, so
  paraphrases without a keyword ("i can't get out of bed these days") still hit.

Judgement calls (documented in the tests):
- "got paid today, pizza!" is not money: no amount, no trouble. "i make 4000 a month" and "i'm
  broke until friday" are.
- Casual "i'm burned out" is not mental_health (burnout as a diagnosis is: "diagnosed with
  burnout", "my burnout"). "i need therapy lol" is a joke, not a category hit; "i'm in therapy" is.
- Tourist visas ("my visa for japan") are not legal; "my visa expires", "work visa", "visa
  status" are. "my visa card" is neither.
- A message that names a mental condition ("diagnosed with depression") is mental_health only,
  not also health; "couples therapy" is relationship only, not also mental_health.
- Quitting a job is work_conflict only when pressure is named ("forced to resign", "pushed out").
"""

from __future__ import annotations

import re
from collections.abc import Sequence

import numpy as np

from hunch.pipeline.checks import fold

_PARTNER = r"(?:wife|husband|girlfriend|boyfriend|partner|fianc[eé]e?|spouse)"
_KIN = (
    r"(?:mom|mum|mother|dad|father|sister|brother|parents?|family|in-laws?|mother-in-law|"
    r"father-in-law|stepmom|stepdad|grandma|grandpa|grandmother|grandfather|son|daughter|kids?)"
)
_BOSS = (
    r"(?:boss|bosses|manager|managers|supervisor|team lead|line manager|director|ceo|"
    r"co-?workers?|colleagues?|workmates?|teammates?|team)"
)
_MENTAL_CONDITIONS = (
    r"depression|anxiety|bipolar|adhd|ptsd|ocd|burnout|autism|schizo\w*|borderline|"
    r"an? (?:eating|anxiety|panic|personality|mood)"
)

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "health": (
        # diagnoses ("diagnosed with cancer"; mental conditions belong to mental_health)
        r"diagnosed with (?!" + _MENTAL_CONDITIONS + r")",
        r"tested (?:positive|negative) for",
        r"(?:i have|i've got|i've had|i got|i'm suffering from|i suffer from|suffers from|has|"
        r"had|have) (?:an? |the )?(?:cancer|diabetes|asthma|epilepsy|tumou?r|migraines|hiv|"
        r"crohn's|lupus|heart disease|high blood pressure|heart condition|arthritis|"
        r"endometriosis|pcos|fibromyalgia|multiple sclerosis|parkinson's|alzheimer's|dementia|"
        r"stroke|heart attack|covid|flu|pneumonia|bronchitis|concussion|kidney stones|"
        r"chronic (?:pain|illness|fatigue|condition))",
        # own medical things
        r"(?:my|her|his|their) (?:diagnosis|prognosis|surgery|operation|chemo(?:therapy)?|"
        r"radiation|biopsy|test results|blood tests?|blood work|mri|x-?ray|colonoscopy|"
        r"mammogram|medication|meds|prescription|blood pressure|blood sugar|cholesterol|"
        r"heart condition|chronic (?:pain|illness|condition|fatigue)|back pain|migraines?|"
        r"asthma|diabetes|doctor|gp|surgeon|oncologist|cardiologist|injury|injuries)",
        r"(?:i'm having|i am having|i had|i have|i need|i'm getting|going in for|booked for) "
        r"(?:an? |my |some )?(?:\w+ )?(?:surgery|operation|biopsy|chemo|chemotherapy|mri|"
        r"colonoscopy)",
        r"recovering from (?:surgery|an? (?:operation|injury|illness|infection|surgery)|"
        r"my (?:surgery|operation|injury|illness))",
        r"i(?:'m| am) (?:currently |now )?(?:pregnant|in remission|infertile|on (?:insulin|"
        r"antibiotics|painkillers|chemo|medication|meds|blood thinners|steroids))",
        r"(?:we're|we are|i'm|i am|my (?:wife|girlfriend|partner) is) (?:expecting|having) "
        r"(?:a|our|another) (?:baby|child|kid)",
        r"(?:my (?:wife|girlfriend|partner)|she) is pregnant|pregnancy test|my pregnancy|"
        r"(?:i|she) (?:had|have had|has had) a miscarriage",
        r"i (?:broke|sprained|tore|fractured|dislocated|pulled|herniated|ruptured|twisted|"
        r"injured) (?:my|a) (?:\w+ )?(?:arm|leg|wrist|ankle|rib|ribs|foot|toe|finger|"
        r"collarbone|nose|back|hip|jaw|shoulder|knee|acl|hand|elbow|neck|skull|tailbone|"
        r"muscle|tendon)",
        r"(?:i'm|i am|i was|he's|she's|he was|she was|my \w+ (?:is|was)) (?:in|admitted to|"
        r"rushed to|taken to) (?:the |a )?(?:hospital|icu|intensive care|er|a&e|emergency room)",
        r"i (?:went|had to go|ended up|got rushed|was rushed) (?:in |to )(?:the )?(?:er|a&e|"
        r"emergency room|hospital|urgent care)",
        r"in and out of (?:the )?(?:hospital|er|a&e)",
        r"i've been (?:feeling )?(?:sick|ill|unwell|nauseous|dizzy|feverish) (?:for|since|all)",
        r"my (?:mom|mum|mother|dad|father|wife|husband|sister|brother|grandma|grandpa|"
        r"grandmother|grandfather|son|daughter|partner|friend|boyfriend|girlfriend) (?:is|was|"
        r"has been|just got|got|has|had) (?:really |very |so |seriously |quite )?(?:terminally "
        r"ill|sick(?! of| and tired)|ill|dying|in a coma|on life support|in hospice|diagnosed|"
        r"undergoing (?:surgery|chemo)|having surgery|in surgery)",
    ),
    "mental_health": (
        r"my (?:therapist|psychiatrist|psychologist|psychotherapist|shrink|counsell?or)",
        r"(?:i|we)(?:'m| am)? (?:see|saw|seeing|started seeing|found|got|have|went to|should "
        r"see) an? (?:new )?(?:therapist|psychiatrist|psychologist|psychotherapist|shrink|"
        r"counsell?or)",
        r"(?:i'm in|i am in|i was in|i've been in|i started|i quit|i stopped|i'm starting|"
        r"i go to|i'm going to|i went to|i've started|i'm considering|i might (?:start|try)|"
        r"my) (?:weekly |regular )?(?:therapy|counsell?ing|therapy sessions?)",
        r"therapy session",
        r"(?:i'm|i am|i've been|i have been|i was|i feel|i'm feeling|been feeling|i got) "
        r"(?:so |really |very |severely |clinically |quite |totally |pretty |kind of |a bit |"
        r"super )?(?:depressed|suicidal)",
        r"i (?:feel|felt|am feeling|'m feeling) (?:so |completely |totally |really )?"
        r"(?:worthless|empty|hopeless|numb|broken inside|like a burden|like giving up)",
        r"(?:my|i have|i've got|i get|i suffer from|suffer from|suffering from|dealing with|"
        r"struggle with|struggling with|struggled with|diagnosed with|living with|a history of) "
        r"(?:(?:so |very |really |pretty |extremely |severe |bad |terrible |awful |crippling |"
        r"constant |chronic |social |general |generalized |clinical |major |mild |serious |"
        r"childhood |postpartum |health |existential )+)?(?:depression|anxiety|ptsd|ocd|"
        r"bipolar|adhd|autism|schizophrenia|borderline personality|bpd|panic disorder|"
        r"an eating disorder|eating disorder|anorexia|bulimia|agoraphobia|psychosis)",
        r"(?:i had|i have|i get|i got|i keep having|i've had|i have had|i am having|i'm "
        r"having|my|having an?|had an?|got an?) (?:an? |these |some |another |bad )*"
        r"(?:panic|anxiety) attacks?",
        r"(?:my|i'm on|i am on|i take|i'm taking|i am taking|i started|i stopped|i quit|came "
        r"off|i'm off|put on|prescribed(?: me)?|i was prescribed|i've been on|i was on|i went "
        r"off) (?:the |some |my |a )?(?:\w+ )?(?:antidepressants?|ssris?|sertraline|prozac|"
        r"zoloft|lexapro|citalopram|escitalopram|fluoxetine|xanax|lithium|adderall|ritalin|"
        r"venlafaxine|wellbutrin|bupropion|valium|diazepam|lorazepam|antipsychotics?|mood "
        r"stabili[sz]ers?|psych meds)",
        r"self[- ]?harm\w*|(?:cutting|hurting|harming) myself|harm myself|hurt myself on purpose",
        r"(?:want|wanted|wanting|thought about|thinking about|thinking of|thoughts of|urge to) "
        r"(?:to )?(?:kill(?:ing)? myself|die|dying|suicide|end(?:ing)? (?:it all|my life)|"
        r"disappear(?:ing)?)",
        r"suicidal (?:thoughts|ideation|feelings)",
        r"(?:don't|do not|dont) want to (?:be here|live|exist|go on)(?: anymore| any more)?",
        r"wish i (?:was|were) dead",
        r"(?:diagnosed with|my|i have|i've got|i got|on (?:sick )?leave for|signed off with|"
        r"off work with) (?:an? )?burn(?:ed|t)?[- ]?out",
        r"my mental (?:health|illness)|mental health (?:issues|struggles|crisis|problems|day)",
    ),
    "money": (
        r"(?:my|our|his|her|their) (?:salary|income|wages?|take-home|net pay|pay cut|pay "
        r"rise|pay raise|raise|bonus|savings|debts?|student (?:loans?|debt)|loans?|mortgage|"
        r"credit card (?:debt|bill)|credit score|overdraft|bank balance|tax bill|financial "
        r"situation|finances|money (?:situation|problems|troubles|issues|worries))",
        r"i (?:earn|make|get paid|took home|take home|bring home|am paid|'m paid) "
        r"(?:about |around |roughly |only |just |less than |more than |over |under |nearly |"
        r"almost |approximately |like )*(?:[$£€]\s?\d|\d[\d,.]*\s?(?:k|grand|thousand|usd|eur|"
        r"gbp|euros?|dollars?|bucks|pounds|quid)\b|\d[\d,.]*\s+(?:a|per|an) "
        r"(?:year|month|week|hour|annum))",
        r"(?:what|how much) (?:i|we) (?:earn|make|owe|get paid)",
        # "i owe you one" is thanks; an amount or a money word is needed
        r"\bi owe (?:\w+ ){0,3}?(?:[$£€]\s?\d|\d[\d,.]*\s?(?:k|grand|thousand|euros?|dollars?|"
        r"bucks|pounds|quid|usd|eur)\b)",
        r"\bi owe (?!you\b)(?:\w+ ){0,3}(?:money|rent|taxes|the bank|back taxes|child support)",
        r"(?:drowning|deep|buried|swimming) in (?:\w+ ){0,2}debt",
        r"(?:i'm|i am|we're|we are|i've been|we've been|i was|we were) (?:so |really |totally "
        r"|completely |flat |dead |currently |still )*(?:broke|in debt|in the red|overdrawn|"
        r"bankrupt|insolvent|drowning in debt|deep in debt|struggling financially|struggling "
        r"to pay)",
        r"(?:can't|cannot|can not|couldn't|unable to) (?:make|pay|afford|cover) (?:the |my "
        r"|our |this month's |next month's |this |next )?(?:rent|mortgage|bills|tuition|"
        r"groceries|medical bills|electricity bill|loan payments?|car payment|installment)",
        r"(?:behind on|late on|missed|fell behind on|skipped) (?:my |the |our |a )?(?:rent|"
        r"mortgage|payments?|bills|loan|credit card payments?)",
        r"rent arrears",
        r"(?:is|are|was) evicting (?:me|us)|(?:got|received|have) an eviction notice",
        r"(?:i'm|we're|i was|we were|i got|we got|facing|my) (?:being )?(?:evicted|eviction|"
        r"foreclosure)",
        r"paycheck to paycheck|make ends meet",
        r"(?:i have|i've got|i'm having|we have|we're having|i've been having|my|our|in|with) "
        r"(?:some |big |serious |major |real |a lot of |so many )?(?:financial|money) (?:trouble"
        r"|troubles|problems|worries|difficulties|issues|struggles|stress|crisis)",
        r"money (?:is|are|'s) (?:really |very |so |super |pretty )?(?:tight|short)|"
        r"(?:short|tight|strapped) (?:on|for) (?:money|cash)",
        r"(?:filed|filing|file) for bankruptcy|went bankrupt|declared bankruptcy",
        r"(?:took out|taking out|applied for|got|need|needed|took) (?:a |another |an )?"
        r"(?:payday |personal |student |bank |car |home )?loans?",
        r"maxed out (?:my |our )?(?:credit )?cards?",
    ),
    "relationship": (
        # exes and breakups; "my ex-boss" is not one
        r"my (?:exes|ex-(?:boyfriend|girlfriend|wife|husband|partner|fianc\w*)|ex\b(?!-))",
        r"(?:we|i|she|he|they) (?:just |finally |recently |officially |both )*(?:broke up|"
        r"split up|got divorced|filed for divorce|are getting divorced|are splitting up)"
        r"(?! (?:the|a|an) )",
        r"(?:my|our|her|his|their) (?:\w+ )?(?:breakup|divorce|separation)",
        r"(?:going through|filing for|got|went through) (?:a |the |my )?(?:messy |nasty |bad "
        r"|painful |ugly |difficult |tough |hard )?(?:breakup|divorce|separation)",
        r"(?:getting|got|am getting|i'm getting) divorced",
        r"(?:dumped|ghosted|cheated on|cheating on|walked out on) me|(?:he|she|they) left me"
        r"(?: for| because| after| last| yesterday| today)",
        r"(?:having|had|has|caught \w+ having|my|his|her|their) (?:an |a )?(?:secret )?affair",
        r"i (?:cheated on|am cheating on|'m cheating on|have cheated on|'ve cheated on) my",
        r"my (?:marriage|relationship|girlfriend|boyfriend|wife|husband|partner|"
        r"fianc[eé]e?)\b[^.!?]{0,30}?\b(?:is falling apart|falling apart|on the rocks|"
        r"is struggling|is in trouble|is toxic|isn't working|is not working|is over|rocky|"
        r"is a mess|is complicated|is unhappy|is abusive|hit me|yells at me|yelled at me|"
        r"screamed at me|cheated|lied to me|wants a divorce|wants to leave|wants to break "
        r"up|is leaving me|is distant|doesn't love me|ignores me|is controlling|is jealous)",
        r"(?:i|we) (?:just |finally |recently )?(?:got|was|were) dumped\b",
        r"my (?:" + _PARTNER + r"|" + _KIN + r") and i (?:are fighting|are going through a "
        r"(?:rough|hard|tough|bad) (?:patch|time)|keep (?:fighting|arguing)|have been "
        r"(?:fighting|arguing)|aren't (?:speaking|talking)|haven't (?:spoken|talked)|got "
        r"into|had a (?:big |huge |bad |terrible |nasty |major |massive )?(?:fight|argument|"
        r"row|blowup|blow-up)|broke up|split|separated|are (?:splitting|separating|getting "
        r"divorced|on a break)|are in a rough patch|are not (?:speaking|talking)|fought|"
        r"argued)",
        r"we (?:keep (?:fighting|arguing)|(?:have been|'ve been) (?:fighting|arguing)|fight "
        r"(?:a lot|all the time|constantly))",
        r"(?:fight|fought|argument|arguments|argued|row|falling out|fell out|feud|beef|big "
        r"fight|huge fight|blowup|blow-up|clash|issues|problems|trouble|tension|drama) with "
        r"my (?:" + _KIN + r"|" + _PARTNER + r"|ex)\b",
        r"(?:haven't|have not|hasn't|don't|do not|no longer|stopped) (?:spoken|talked|speak|"
        r"talk|speaking|talking) to my (?:mom|mum|mother|dad|father|sister|brother|parents|"
        r"family|son|daughter|wife|husband|ex|in-laws)",
        r"my (?:mom|mum|mother|dad|father|parents|family|sister|brother|in-laws) (?:disowned|"
        r"kicked me out|cut me off|abandoned|abused|hit|beat|yelled at|screamed at|shouts "
        r"at|won't speak to|stopped talking to|threw me out|is toxic|are toxic)",
        r"estranged from my",
        r"my (?:parents|mom and dad) (?:are |just |finally )?(?:getting divorced|divorcing|"
        r"separating|splitting up|got divorced|separated|divorced)",
        r"couples (?:therapy|counsell?ing)|marriage (?:counsell?ing|therapy)",
        r"my love life",
    ),
    "sexuality": (
        r"\bi(?:'m| am| think i'm| think i am| might be| may be| think i might be| realized "
        r"i'm| realised i'm| am pretty sure i'm| 'm pretty sure i'm) (?:a |an |also |totally "
        r"|definitely |completely |actually |really |quite |probably |kind of |sort of )*"
        r"(?:gay|lesbian|bisexual|bi|pansexual|asexual|queer|transgender|trans|non-?binary|"
        r"enby|genderfluid|genderqueer|intersex|demisexual|aromantic|closeted)(?![-\w])",
        r"(?:i|he|she|they|we)(?:'m| am| just| finally| recently)? (?:came|coming|come) out "
        r"(?:to|as|of the closet|last (?:year|month|week)|(?:\d+ )?years? ago|a (?:year|month|few)"
        r"|in (?:high school|college|\d{4}))\b|came out as\b|coming out as\b|"
        r"coming out to (?:my|your|our)\b",
        r"my (?:sexuality|sexual orientation|gender identity|gender dysphoria|pronouns|"
        r"sex life|libido|sex drive|virginity|kinks?|fetish(?:es)?|body count|sexual "
        r"(?:health|history|fantasies|orientation|identity))",
        r"my (?:gender |medical |social )transition|my transition (?:journey|surgery|"
        r"timeline|process)|(?:my|starting|i'm on|i started|on) hrt\b|top surgery|bottom "
        r"surgery|gender dysphoria|gender-affirming",
        r"i(?:'m| am| was| have been|'ve been)? (?:only |also |mostly |not |never |sometimes "
        r"|always |kinda |really |just )*(?:attracted to|into|slept with|hooked up with|"
        r"hooking up with|sleeping with) (?:both |other |some )?(?:men|women|guys|girls|boys"
        r"|a guy|a girl|a man|a woman|the same sex|someone of the same|people of the same)",
        r"(?:we|i) (?:(?:just|finally|never|rarely|barely|still|only|even|haven't|have not|"
        r"hadn't|didn't|don't|do not|can't|couldn't|have|had|'ve) )*(?:had|have|having|"
        r"stopped having|started having) sex\b",
        r"lost my virginity|i(?:'m| am) (?:still )?a virgin|erectile|one[- ]night stand|"
        r"sexting|low libido|porn addiction|addicted to porn",
        r"my (?:son|daughter|brother|sister|child|kid|dad|mom|father|mother|best friend|"
        r"friend|cousin|uncle|aunt|partner|boyfriend|girlfriend|husband|wife) (?:is|just came "
        r"out as|came out as|came out|told me (?:he|she|they)(?:'s| is| are)) (?:\w+ )?(?:gay"
        r"|lesbian|bisexual|trans|transgender|queer|non-?binary)",
        r"questioning my (?:sexuality|gender|orientation)",
    ),
    "legal": (
        r"(?:i|i've|i'm|i am|i was|i got|my \w+) (?:have |has |is |was |got |just got |been "
        r"|being |getting |gotten )*(?:arrested|charged with|convicted|indicted|sentenced|"
        r"deported|put on probation|jailed|detained by (?:police|immigration|ice))",
        r"(?:my|have a|has a|got a) criminal record|criminal charges",
        r"(?:got|have|had|received) an? (?:dui|dwi)\b",
        r"(?:my|our|his|her|their) (?:court (?:date|case|hearing|appearance)|hearing date|"
        r"lawyer|attorney|solicitor|barrister|lawsuit|legal (?:troubles?|problems|issues|"
        r"fees|case)|custody (?:battle|hearing|case|dispute)|parole|parole officer|"
        r"probation officer|bail|bail hearing|duis?|dwi|indictment|subpoena|divorce lawyer|"
        r"immigration (?:lawyer|case|hearing|appointment|interview|status|officer)|visa "
        r"(?:status|application|interview|appointment|renewal|extension)|residence permit|"
        r"residency permit|work permit|work visa|student visa|green card|greencard|asylum "
        r"(?:claim|case|application|hearing)|citizenship (?:application|test|interview))",
        r"(?:my|our) trial(?!\s+(?:period|subscription|run|version|account|membership|plan|"
        r"license))",
        r"(?:my|our) probation(?!\s+period)",
        r"my visa(?! (?:card|debit|credit|payment|statement|bill|app\b))(?!\s+for\b)",
        r"(?:i'm|i am|we're|we are|i was|we were|i got|we got|i'm being|we're being|i'm "
        r"getting) (?:suing|sued|being sued|getting sued)|(?:is|are|was|were) (?:suing|"
        r"sued) (?:me|us)|(?:suing|sued) (?:me|us|my \w+)|lawsuit against (?:me|us)|filed a "
        r"(?:lawsuit|police report|restraining order)|restraining order|took me to court",
        r"police (?:came to|showed up (?:at|to)|questioned|stopped|pulled|called|arrested|"
        r"searched|raided|knocked on|interrogated|detained|fined|charged|cautioned) "
        r"(?:me|us|my|our)",
        r"i (?:called|phoned|reported (?:it|him|her|them|this|that) to|went to|talked to|"
        r"spoke to|spoke with|was questioned by|got questioned by|got stopped by|got pulled "
        r"over by|was stopped by|was interviewed by) (?:the |a )?(?:police|cops|cop|officers"
        r"|detectives|sheriff)",
        r"(?:going to|go to|have to go to|due in|due at|appear(?:ing)? in|appeared in|was in"
        r"|am in|i'm in|summoned to|taken to|dragged to|had to go to|testify in|testified in"
        r"|testifying in|ordered to appear in) court\b(?! to play)",
        r"(?:i'm|i am|i was|i went|i got sent|my \w+ (?:is|was|went|got sent)) (?:in|to|into"
        r"|out of) (?:jail|prison)",
        r"(?:i'm|i am|we're|we are|i could be|i might be|facing|risk of being|afraid of being"
        r"|scared of being|worried about being|threatened with|got|was|been) (?:being )?"
        r"(?:deported|deportation)|undocumented|overstay(?:ed|ing)? (?:my|our) "
        r"(?:visa|stay|permit)",
        r"(?:my|our) (?:visa|permit|residency|residence permit|papers) (?:expired|expires|"
        r"expiring|ran out|runs out|got rejected|was rejected|was denied|got denied|is "
        r"expiring|is about to expire|has expired|isn't valid)",
        r"(?:visa|asylum|residency|citizenship) (?:application |claim )?(?:got |was |has "
        r"been |just got )?(?:rejected|denied|refused|revoked)",
        r"applied for (?:asylum|citizenship|residency|permanent residence|a green card|a "
        r"work permit)",
    ),
    "work_conflict": (
        # being fired; "fired up" is enthusiasm
        r"(?:i|i've|i'm|i am|i was|i got|i get|i just got|i'll get|i'll be|i might (?:get|be)"
        r"|i could (?:get|be)|going to get|gonna get|about to get|afraid of getting|scared "
        r"of getting|worried about getting|worried i'll get|fear i'll get|they|my boss|my "
        r"manager|my employer|the company|hr|got|been|being|getting|was|were|am) (?:(?:finally"
        r"|just|recently|actually|basically|probably|totally|officially|literally|already|"
        r"so|also|both|then|now|be|been|being|getting|got|get|really|even|almost|nearly|"
        r"barely|gonna|going to|about to|might|could|may|will|would|would've|should've|"
        r"kind of) )*(?:fired|laid off|sacked|made redundant|axed|canned|demoted|terminated|"
        r"dismissed)\b(?! up\b)",
        r"(?:they|my boss|my manager|the company|hr|management|my employer) (?:just |finally"
        r" |recently )?(?:let|laid|sacked|fired|cut) me (?:go|off|out)(?!\s*(?:home|to|first"
        r"|on|early|in|with|now|ahead)\b)",
        r"(?:got|been|was|being) let go\b(?! of)",
        r"performance improvement plan|(?:on|put on|placed on) a pip\b|disciplinary "
        r"(?:hearing|meeting|action|procedure|process|letter|warning)|(?:written|formal|final"
        r"|verbal) warning|warning letter|(?:got|received|given|issued) a warning at work",
        r"\bhr (?:called|complaint|meeting|investigation|investigating|wants|summoned|got "
        r"involved|warned)|(?:reported|complained) (?:me|him|her|them|it|about \w+)? ?to hr|"
        r"went to hr|(?:called|talk(?:ed|ing) to|spoke to|meeting with) hr\b",
        r"(?:got|was|being|am being) (?:suspended (?:from work|without pay)|written up)|"
        r"under investigation at work",
        r"(?:i hate|i can't stand|i cannot stand|i despise|fed up with|so done with|sick of"
        r"|tired of|can't deal with|struggling with|dealing with|clashing with|clash with|"
        r"beef with|problem with|problems with|trouble with|issues? with|conflict with|"
        r"conflicts with|fight with|fought with|argument with|argued with|arguing with|"
        r"fighting with|falling out with|fell out with|feud with|tension with|bad blood "
        r"with|drama with|disagreement with|disagreed with) my (?:\w+ )?" + _BOSS,
        r"my " + _BOSS + r"\b[^.!?\n]{0,40}?\b(?:yell(?:ed|s|ing)?|scream(?:ed|s|ing)?|"
        r"shout(?:ed|s|ing)?|bull(?:y|ies|ied|ying)|humiliat\w+|undermin\w+|harass\w*|"
        r"micromanag\w+|belittl\w+|insult\w*|badmouth\w*|sabotag\w+|gaslight\w*|threaten\w*|"
        r"blam(?:ed|es|ing)|tak(?:e|es|ing|en|ook) (?:all |the |my )?credit|"
        r"steal(?:s|ing)? (?:my )?credit|stole my (?:idea|credit|work)|throw(?:s|ing)? me "
        r"under|threw me under|ignor(?:ed|es|ing) me|talks? down|talked down|hates me|hate me|"
        r"is toxic|are toxic|is a nightmare|is impossible|"
        r"is a tyrant|is abusive|is a jerk|is an idiot|is awful|is horrible|is terrible|is "
        r"unbearable|is out to get me|is being (?:unfair|a jerk|rude|mean|nasty|difficult|"
        r"toxic)|wrote me up|reported me|gave me a (?:warning|bad review|terrible review)|"
        r"passed me over|overlooked me|embarrassed me|called me out|chewed me out|dressed "
        r"me down|criticized me|shamed me|accused me|lied about me|spread rumou?rs|"
        r"excluded me|froze me out)",
        r"(?:toxic|hostile) (?:workplace|work environment|work culture|office|job)|"
        r"(?:bullied|harassed|discriminated against|gaslit|mobbed|micromanaged|undermined) "
        r"(?:at work|at the office|by my (?:boss|manager|coworkers?|team))",
        r"(?:forced|pushed|pressured|bullied|driven) (?:me )?(?:out|to (?:quit|resign|"
        r"leave))|(?:forced|pushed|pressured|bullied) (?:me )?(?:into|to) "
        r"(?:quitting|resigning)|constructive dismissal|(?:had to|have to|was forced to|am "
        r"forced to|felt forced to) resign",
        r"i (?:just |recently )?lost my job",
        r"passed over for (?:a |the )?(?:promotion|raise|job|position)|denied (?:a |the |my )?"
        r"(?:promotion|raise)",
    ),
    "religion_politics": (
        r"(?:my|his|her|their) (?:faith(?! in\b)|religion|religious (?:beliefs?|views|"
        r"upbringing|doubts|crisis)|beliefs|church|mosque|synagogue|pastor|priest|imam|rabbi|"
        r"congregation|spiritual (?:journey|life)|prayer life|bible study)",
        r"crisis of faith",
        r"(?:lost|losing|regain(?:ed|ing)?|doubt(?:ing|ed)?|questioning|struggling with|"
        r"struggle with|reconsidering|rediscover(?:ed|ing)?|found|finding|left|leaving|"
        r"abandoned|rejected|renounced) (?:my |our |the |his |her )?(?:faith(?! in\b)|"
        r"religion|beliefs?|god|church|islam|christianity|judaism|hinduism|buddhism)",
        r"\bi(?:'m| am| was raised| was brought up| converted to| have converted to| became| "
        r"just became| recently became| am now|'m now|'ve become| have become) (?:in |as )?"
        r"(?:a |an |also )?(?:devout |practicing |practising |born[- ]again |lapsed |non-?"
        r"practicing |strict |orthodox |secular |reform |conservative |observant )*"
        r"(?:christian|muslim|jewish|catholic|protestant|atheist|agnostic|hindu|buddhist|sikh"
        r"|mormon|evangelical|pagan|wiccan|religious|spiritual|jew|baptist|methodist|lutheran"
        r"|anglican|presbyterian|pentecostal|jehovah's witness|humanist|islam|judaism)\b",
        r"i (?:go to|attend|attended|used to go to|stopped going to|quit going to|"
        r"observe|observed|celebrate|celebrated) (?:\w+ )?(?:church|mosque|synagogue|mass|"
        r"temple|friday prayers|ramadan|shabbat|sabbath|lent|bible study|sunday school)",
        r"i (?:pray|prayed) (?:every|daily|five times|before|each|at night|a lot|regularly)",
        r"my (?:political|politics|political (?:views?|opinions?|beliefs?|leanings?|party|"
        r"affiliation|stance|convictions|activism))\b",
        r"my activism|i canvass(?:ed|ing)? for|i'm campaigning for|i campaign for",
        r"i (?:voted|vote|am voting|'m voting|will vote|would vote|always vote|never vote|"
        r"didn't vote) (?:for |against )?(?:\w+ ){0,2}(?:trump|biden|harris|obama|clinton|"
        r"sanders|macron|le pen|labour|conservatives?|tories|tory|lib dems?|greens?|"
        r"republicans?|democrats?|gop|snp|afd|cdu|spd|fdp|brexit|remain|leave|the left|the "
        r"right|libertarian|socialists?|communists?)\b",
        r"i (?:voted|didn't vote|did not vote|couldn't vote|can't vote) in the (?:election|"
        r"referendum|primary|primaries)",
        r"\bi(?:'m| am| became| have become|'ve become| consider myself| identify as| lean|"
        r"'m leaning) (?:a |an |very |pretty |quite |fairly |super |really |staunch |proud |"
        r"lifelong |registered |card-carrying |strongly |politically )*(?:conservative|"
        r"liberal|socialist|communist|libertarian|leftist|left-wing|right-wing|republican|"
        r"democrat|fascist|anarchist|progressive|nationalist|centrist|marxist|maga|feminist|"
        r"activist|environmentalist|monarchist|populist|social democrat|tory|labour|lib dem)"
        r"\b(?!\s+(?:with|about|in|when|on|eater)\b)",
        r"i (?:went to|joined|attended|organi[sz]ed|took part in|participated in|marched in) "
        r"(?:a |an |the |this |last week's |yesterday's |another )?(?:\w+ ){0,2}?(?:protest|"
        r"demonstration|rally|march)\b",
    ),
}

CATEGORY_PROTOTYPES: dict[str, tuple[str, ...]] = {
    "health": (
        "The doctor told me I have type 2 diabetes and I have to change my diet.",
        "I'm having knee surgery next month and I'm nervous about the recovery.",
        "My dad was diagnosed with cancer last week.",
        "I've had a terrible migraine for three days and the painkillers aren't helping.",
        "We just found out I'm pregnant, we haven't told anyone yet.",
        "My blood pressure is too high so they put me on tablets.",
    ),
    "mental_health": (
        "I've been so depressed lately that I can barely get out of bed.",
        "My therapist thinks I should try a different kind of medication.",
        "I had another panic attack on the train this morning.",
        "I've been having really dark thoughts and I don't know who to tell.",
        "I started seeing a psychiatrist because my anxiety is out of control.",
        "Some days I feel completely empty and numb, like nothing matters.",
    ),
    "money": (
        "I can't make rent this month and I don't know what to do.",
        "I owe my brother about five thousand euros and I can't pay him back.",
        "I earn barely enough to cover my bills, let alone save anything.",
        "We're drowning in credit card debt.",
        "I'm so broke that I skipped lunch all week to save money.",
        "My salary got cut by twenty percent and I'm panicking about the mortgage.",
    ),
    "relationship": (
        "My girlfriend and I broke up last night and I feel awful.",
        "I think my husband is cheating on me.",
        "My wife and I keep having the same fight over and over.",
        "I haven't spoken to my mother in two years after our big argument.",
        "My ex keeps texting me and it's messing with my head.",
        "We're getting a divorce and the kids don't know yet.",
    ),
    "sexuality": (
        "I think I might be gay but I haven't told anybody.",
        "I came out to my parents last weekend.",
        "I'm attracted to both men and women and I'm still figuring it out.",
        "My sex life has been nonexistent since the baby was born.",
        "I've started the process of transitioning and I'm scared to tell my family.",
        "I'm asexual and people never believe me when I say it.",
    ),
    "legal": (
        "I got arrested last night and I have to go before a judge on Monday.",
        "My visa runs out in two months and my application is still pending.",
        "A neighbour is suing me and I had to hire a lawyer.",
        "The police showed up at my door asking questions about my brother.",
        "I have a court date next week about the custody case.",
        "I'm scared I'll be deported if they check my papers.",
    ),
    "work_conflict": (
        "I got fired today after six years at the company.",
        "My boss humiliated me in front of the whole team again.",
        "HR called me in because a coworker complained about me.",
        "They put me on a performance improvement plan and I think they want me gone.",
        "I got a written warning and I don't even know what I did wrong.",
        "I was pushed to resign after I stood up to my manager.",
    ),
    "religion_politics": (
        "I've been losing my faith and I don't know who to talk to about it.",
        "I voted for the other party this time and my family is furious.",
        "I pray every morning, it keeps me grounded.",
        "I went to the climate march last weekend, it meant a lot to me.",
        "I grew up very religious but now I don't believe in God anymore.",
        "I'm a committed socialist and it causes arguments at every family dinner.",
    ),
}


def _compile(fragments: Sequence[str]) -> re.Pattern[str]:
    return re.compile(r"\b(?:" + "|".join(f"(?:{f})" for f in fragments) + r")\b")


_COMPILED: dict[str, re.Pattern[str]] = {
    cat: _compile(frags) for cat, frags in CATEGORY_KEYWORDS.items()
}


def _check_known(categories: Sequence[str]) -> None:
    for cat in categories:
        if cat not in CATEGORY_KEYWORDS or cat not in CATEGORY_PROTOTYPES:
            raise ValueError(
                f"category {cat!r} has no keywords or prototypes in privacy.categories"
            )


def keyword_categories(text: str, categories: Sequence[str]) -> list[str]:
    """The categories (in the order of `categories`) with a personal-framing keyword hit."""
    _check_known(categories)
    folded = fold(text)
    return [cat for cat in categories if _COMPILED[cat].search(folded)]


class CategoryDetector:
    """Keyword OR embedding-prototype similarity, per category (Phase 5)."""

    def __init__(self, categories: Sequence[str], embedder, min_similarity: float) -> None:
        _check_known(categories)
        self.categories = tuple(categories)
        self.min_similarity = min_similarity
        self._prototypes: dict[str, np.ndarray] = {}
        if embedder is not None:
            texts = [t for cat in self.categories for t in CATEGORY_PROTOTYPES[cat]]
            vectors = np.asarray(embedder.embed_documents(texts), dtype=np.float32)
            at = 0
            for cat in self.categories:
                n = len(CATEGORY_PROTOTYPES[cat])
                self._prototypes[cat] = vectors[at : at + n]
                at += n

    def similarities(self, query_vec: np.ndarray | None) -> dict[str, float]:
        """Per category, the max dot product of `query_vec` with its prototype vectors."""
        if not self._prototypes or query_vec is None:
            return {}
        q = np.asarray(query_vec, dtype=np.float32).reshape(-1)
        return {cat: float(np.max(vecs @ q)) for cat, vecs in self._prototypes.items()}

    def detect(self, text: str, query_vec: np.ndarray | None) -> list[str]:
        by_keyword = set(keyword_categories(text, self.categories))
        sims = self.similarities(query_vec)
        return [
            cat
            for cat in self.categories
            if cat in by_keyword or sims.get(cat, -1.0) >= self.min_similarity
        ]
