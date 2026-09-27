"""The Conversation — the chat front door to every module (run 14).

One message in, one reply out. A deterministic router (no model needed, keyless) sends the
message to the right tool and says which tools it used (`trace`):

- a legal question            -> The Answer Contract (quotes from The Library, or abstains)
- "what about 15 Sep 2024?"   -> the previous question, re-asked on the new as-of date + diff
- "timeline of Rule 170"      -> The Status Ledger, every dated segment with its evidence
- benefit share / turnover    -> The Passport Compiler's ABS calculator (asks for the amount)
- checklist / passport        -> The Passport Compiler (asks for the product category)
- "check this ad: ..."        -> The Claim Sentry (risk indicators only, never a rewrite)
- "compare with static RAG"   -> the static-RAG baseline beside our answer
- general Ayurveda questions  -> curated background (offline) + optional LLM, never law

The router never lets a general-knowledge path answer a legal question: if a message looks
legal and The Library has no source, the reply is an abstention (KERNEL 7.3).
"""

from __future__ import annotations

import datetime as dt
import re
import time
from functools import lru_cache
from pathlib import Path

import yaml

from api import ledger
from api.answer import answer, best_span
from api.baseline import retrieve as static_retrieve
from api.chat import llm, sentry
from api.chat.dates import find_date, is_follow_up
from api.passport import abs as abs_calc
from api.passport import categories as passport_cat
from api.retriever import default_index, tokenize
from api.synth import synthesize

KNOWLEDGE_PATH = Path(__file__).resolve().parent / "knowledge.yaml"
CRORE, LAKH = 10_000_000, 100_000

# ---------------------------------------------------------------- localisation of fixed text
T = {
    "en": {
        "hello": "Namaste! 🙏 I'm **Sahayak**, your Ayurveda IP & regulatory guide. I answer from "
        "official sources *as of the date you pick* — and I say so when I don't know.",
        "thanks": "You're welcome! Ask me anything else — try changing the date to see the law "
            "change.",
        "abstain": "I couldn't find an official source in The Library that answers this for "
        "**{jur}** as of **{date}** — so I won't guess. That's on purpose: I never invent law.",
        "status": "As of **{date}**, **{inst}**: {plain}",
        "overlay": "Separately, the **DMR Act, 1954** bans advertising a medicine as a treatment "
        "for the diseases on its Schedule — and this question names one ({diseases}). "
        "That does not depend on Rule 170's date.",
        "found": "I found **{n}** verbatim passage(s) in The Library for **{jur}** as of "
            "**{date}**.",
        "quotes": "The quotes below are the real authority — copied word-for-word, with links.",
        "changed": "⚡ **The law changed** between {a} and {b}: *{s1}* → *{s2}*.",
        "same": "Same status as on {a} — the date you picked falls in the same legal period.",
        "timeline": "Here is the full dated history of **{inst}** from The Status Ledger. Tap any "
        "period to ask about that date.",
        "abs_ask": "Sure — I'll calculate the ABS benefit share under the **Biological Diversity "
        "Regulations, 2025**. What is the company's **annual turnover**? (e.g. *₹3 crore*, "
        "*₹40 crore*, *₹150 crore*)",
        "abs": "For a turnover of **{amt}** as of **{date}**, the applicable slab is "
        "**{slab}** → rate **{rate}%**. Arithmetic and sources below.",
        "abs_abstain": "The ABS Regulations 2025 were not in force on **{date}**, so I won't "
            "compute a "
        "2025 slab for that date.",
        "pp_ask": "Which kind of product? **Classical** (made exactly as in an authoritative "
        "text), **Proprietary** (your own formula from classical ingredients) or "
        "**Phytopharmaceutical** (standardised plant extract)?",
        "pp": "Here is the **{title}** compliance passport as of **{date}** — {n} obligations, "
        "each with its legal source. You can print it.",
        "claim_ask": "Paste the advertisement, label or tagline text and I'll scan it with **The "
        "Claim Sentry** against the DMR Act, 1954.",
        "claim": "The Claim Sentry found **{n}** risk indicator(s). Highlighted words below, each "
        "with the exact provision. I flag — I never rewrite, and a professional decides.",
        "claim_none": "The Claim Sentry found **no** DMR Act risk indicators in this text. That is "
        "not a clearance — other laws and a human review still apply.",
        "compare": "Here is the same question through an **ordinary (static) RAG** chatbot next to "
        "Sahayak. The static one ignores the date and the ledger.",
        "compare_none": "Ask me a legal question first, then say *compare* to see what an ordinary "
            "chatbot would do.",
        "library": "**The Library** holds **{docs} official documents** ({chunks} passages), "
        "corpus version `{ver}`. Every answer quotes one of these.",
        "switched_date": "🕰️ Time-travelled to **{date}**{note}.",
        "switched_jur": "🌐 Switched jurisdiction to **{jur}**.",
        "date_only": "🕰️ As-of date set to **{date}**. Now ask me a question — I'll answer with "
            "the law of that day.",
        "general": "",
        "general_none": "I don't have a reliable answer to that offline, and I won't make one up. "
        "Try one of these:",
        "medical": "⚕️ I can't advise on treatment or doses. Please consult a qualified doctor or "
            "a "
        "registered Ayurveda practitioner (BAMS).",
        "bg_label": "Background knowledge — not from The Library, not medical or legal advice.",
        "mid-month": " (you gave a month, so I used the 15th)",
        "mid-year": " (you gave a year, so I used 30 June)",
    },
    "hi": {
        "hello": "नमस्ते! 🙏 मैं **सहायक** हूँ — आयुर्वेद IP और नियामक मार्गदर्शक। मैं आपकी चुनी "
            "*तारीख* के "
        "अनुसार आधिकारिक स्रोतों से उत्तर देता हूँ — और जब नहीं पता, तो साफ़ कहता हूँ।",
        "thanks": "आपका स्वागत है! कुछ और पूछिए — तारीख बदलकर कानून बदलते देखिए।",
        "abstain": "**{jur}** के लिए **{date}** तक की लाइब्रेरी में इसका कोई आधिकारिक स्रोत नहीं "
            "मिला — "
        "इसलिए मैं अनुमान नहीं लगाऊँगा। यह जानबूझकर है: मैं कभी कानून नहीं गढ़ता।",
        "status": "**{date}** को, **{inst}**: {plain}",
        "overlay": "अलग से, **DMR अधिनियम, 1954** अपनी अनुसूची की बीमारियों के इलाज के रूप में दवा "
            "के "
        "विज्ञापन पर रोक लगाता है — और इस प्रश्न में उनमें से एक है ({diseases})।",
        "found": "लाइब्रेरी में **{jur}**, **{date}** के लिए **{n}** शब्दशः अंश मिले।",
        "quotes": "नीचे दिए उद्धरण ही असली प्रमाण हैं — शब्दशः, लिंक सहित।",
        "changed": "⚡ **कानून बदल गया** {a} और {b} के बीच: *{s1}* → *{s2}*।",
        "same": "{a} जैसी ही स्थिति — चुनी गई तारीख उसी कानूनी अवधि में है।",
        "timeline": "यह **{inst}** का पूरा दिनांकित इतिहास है (स्टेटस लेजर से)। किसी भी अवधि पर "
            "टैप करें।",
        "abs_ask": "ज़रूर — मैं **जैव विविधता विनियम, 2025** के तहत ABS लाभ-साझा गणना करूँगा। "
            "कंपनी का "
        "**वार्षिक टर्नओवर** क्या है? (जैसे *₹3 करोड़*, *₹40 करोड़*)",
        "abs": "**{amt}** टर्नओवर के लिए **{date}** को लागू स्लैब **{slab}** → दर **{rate}%**। "
            "गणना और स्रोत नीचे।",
        "abs_abstain": "**{date}** को ABS विनियम 2025 लागू नहीं थे, इसलिए मैं गणना नहीं करूँगा।",
        "pp_ask": "किस प्रकार का उत्पाद? **Classical** (शास्त्रीय), **Proprietary** (स्वयं का "
            "फ़ॉर्मूला) या "
        "**Phytopharmaceutical**?",
        "pp": "यह **{date}** तक का **{title}** अनुपालन पासपोर्ट है — {n} दायित्व, हर एक का कानूनी "
            "स्रोत।",
        "claim_ask": "विज्ञापन या लेबल का पाठ पेस्ट करें — मैं **क्लेम सेंट्री** से DMR अधिनियम के "
            "विरुद्ध जाँच करूँगा।",
        "claim": "क्लेम सेंट्री को **{n}** जोखिम संकेत मिले। मैं केवल चिह्नित करता हूँ, कभी बदलता "
            "नहीं।",
        "claim_none": "कोई DMR जोखिम संकेत नहीं मिला। यह मंज़ूरी नहीं है — मानवीय समीक्षा ज़रूरी "
            "है।",
        "compare": "वही प्रश्न एक **साधारण (स्टैटिक) RAG** चैटबॉट से — यह तारीख और लेजर को "
            "नज़रअंदाज़ करता है।",
        "compare_none": "पहले कोई कानूनी प्रश्न पूछें, फिर *compare* कहें।",
        "library": "**लाइब्रेरी** में **{docs} आधिकारिक दस्तावेज़** ({chunks} अंश) हैं, संस्करण "
            "`{ver}`।",
        "switched_date": "🕰️ तारीख बदलकर **{date}** की गई{note}।",
        "switched_jur": "🌐 क्षेत्राधिकार **{jur}** किया गया।",
        "date_only": "🕰️ तारीख **{date}** सेट की गई। अब प्रश्न पूछिए।",
        "general": "",
        "general_none": "इसका विश्वसनीय उत्तर मेरे पास ऑफ़लाइन नहीं है, और मैं गढ़ूँगा नहीं। इनमें "
            "से कुछ आज़माएँ:",
        "medical": "⚕️ मैं इलाज या खुराक की सलाह नहीं दे सकता। कृपया योग्य डॉक्टर या पंजीकृत "
            "आयुर्वेद चिकित्सक (BAMS) से मिलें।",
        "bg_label": "सामान्य जानकारी — लाइब्रेरी से नहीं; चिकित्सीय या कानूनी सलाह नहीं।",
        "mid-month": " (महीना दिया था, इसलिए 15 तारीख ली)",
        "mid-year": " (वर्ष दिया था, इसलिए 30 जून लिया)",
    },
    "gu": {
        "hello": "નમસ્તે! 🙏 હું **સહાયક** છું — આયુર્વેદ IP અને નિયમનકારી માર્ગદર્શક. હું તમે પસંદ "
            "કરેલી "
        "*તારીખ* મુજબ સત્તાવાર સ્ત્રોતોમાંથી જવાબ આપું છું — અને ખબર ન હોય ત્યારે સ્પષ્ટ કહું છું.",
        "thanks": "આપનું સ્વાગત છે! બીજું કંઈ પૂછો — તારીખ બદલીને કાયદો બદલાતો જુઓ.",
        "abstain": "**{jur}** માટે **{date}** સુધીની લાઇબ્રેરીમાં આનો કોઈ સત્તાવાર સ્ત્રોત મળ્યો "
            "નથી — "
        "તેથી હું અનુમાન નહીં કરું. હું ક્યારેય કાયદો ઘડતો નથી.",
        "status": "**{date}** ના રોજ, **{inst}**: {plain}",
        "overlay": "અલગથી, **DMR અધિનિયમ, 1954** તેની અનુસૂચિના રોગોની સારવાર તરીકે દવાની જાહેરાત "
            "પર "
        "પ્રતિબંધ મૂકે છે — અને આ પ્રશ્નમાં તેમાંનો એક છે ({diseases}).",
        "found": "લાઇબ્રેરીમાં **{jur}**, **{date}** માટે **{n}** શબ્દશઃ અંશો મળ્યા.",
        "quotes": "નીચેના અવતરણો જ ખરો આધાર છે — શબ્દશઃ, લિંક સાથે.",
        "changed": "⚡ **કાયદો બદલાયો** {a} અને {b} વચ્ચે: *{s1}* → *{s2}*.",
        "same": "{a} જેવી જ સ્થિતિ — પસંદ કરેલી તારીખ એ જ કાનૂની સમયગાળામાં છે.",
        "timeline": "આ **{inst}** નો સંપૂર્ણ તારીખવાર ઇતિહાસ છે. કોઈપણ સમયગાળા પર ટેપ કરો.",
        "abs_ask": "ચોક્કસ — **જૈવ વિવિધતા નિયમો, 2025** હેઠળ ABS ગણતરી કરીશ. કંપનીનું **વાર્ષિક "
            "ટર્નઓવર** "
        "કેટલું છે? (જેમ કે *₹3 કરોડ*, *₹40 કરોડ*)",
        "abs": "**{amt}** ટર્નઓવર માટે **{date}** ના રોજ સ્લેબ **{slab}** → દર **{rate}%**. ગણતરી "
            "અને સ્ત્રોતો નીચે.",
        "abs_abstain": "**{date}** ના રોજ ABS નિયમો 2025 અમલમાં ન હતા, તેથી ગણતરી નહીં કરું.",
        "pp_ask": "કયા પ્રકારનું ઉત્પાદન? **Classical**, **Proprietary** કે "
            "**Phytopharmaceutical**?",
        "pp": "આ **{date}** સુધીનો **{title}** અનુપાલન પાસપોર્ટ છે — {n} જવાબદારીઓ, દરેકનો કાનૂની "
            "સ્ત્રોત.",
        "claim_ask": "જાહેરાત કે લેબલનો લખાણ પેસ્ટ કરો — **ક્લેમ સેન્ટ્રી** DMR અધિનિયમ સામે તપાસ "
            "કરશે.",
        "claim": "ક્લેમ સેન્ટ્રીને **{n}** જોખમ સંકેતો મળ્યા. હું ફક્ત ચિહ્નિત કરું છું, ક્યારેય "
            "બદલતો નથી.",
        "claim_none": "કોઈ DMR જોખમ સંકેત મળ્યો નથી. આ મંજૂરી નથી — માનવ સમીક્ષા જરૂરી છે.",
        "compare": "એ જ પ્રશ્ન એક **સામાન્ય (સ્ટેટિક) RAG** ચેટબોટથી — તે તારીખ અને લેજરને અવગણે "
            "છે.",
        "compare_none": "પહેલાં કોઈ કાનૂની પ્રશ્ન પૂછો, પછી *compare* કહો.",
        "library": "**લાઇબ્રેરી** માં **{docs} સત્તાવાર દસ્તાવેજો** ({chunks} અંશો) છે, આવૃત્તિ "
            "`{ver}`.",
        "switched_date": "🕰️ તારીખ બદલીને **{date}** કરી{note}.",
        "switched_jur": "🌐 અધિકારક્ષેત્ર **{jur}** કર્યું.",
        "date_only": "🕰️ તારીખ **{date}** સેટ કરી. હવે પ્રશ્ન પૂછો.",
        "general": "",
        "general_none": "આનો વિશ્વસનીય જવાબ મારી પાસે ઑફલાઇન નથી, અને હું ઘડીશ નહીં. આમાંથી કંઈક "
            "અજમાવો:",
        "medical": "⚕️ હું સારવાર કે ડોઝની સલાહ આપી શકતો નથી. કૃપા કરીને લાયક ડૉક્ટર અથવા નોંધાયેલ "
            "આયુર્વેદ ચિકિત્સક (BAMS) ની સલાહ લો.",
        "bg_label": "સામાન્ય માહિતી — લાઇબ્રેરીમાંથી નહીં; તબીબી કે કાનૂની સલાહ નહીં.",
        "mid-month": " (મહિનો આપ્યો હતો, તેથી 15 તારીખ લીધી)",
        "mid-year": " (વર્ષ આપ્યું હતું, તેથી 30 જૂન લીધું)",
    },
}

# Restates The Status Ledger code only; never adds a legal fact (run-13 plain-layer rule).
PLAIN_STATUS = {
    "en": {
        "in_force": "the rule was part of the law and **applied**.",
        "omitted": "the rule had been **deleted** by a government notification, so it did not "
            "apply.",
        "in_force_stayed_omission": "the government had deleted the rule, but the **Supreme Court "
        "paused that deletion** — so the rule still applied while the "
        "case was pending (*sub judice*).",
        "omitted_stay_vacated": "the Supreme Court **closed the case and cancelled its pause**, so "
        "the rule stays deleted.",
    },
    "hi": {
        "in_force": "नियम कानून का हिस्सा था और **लागू** था।",
        "omitted": "सरकारी अधिसूचना से नियम **हटा दिया गया** था, इसलिए लागू नहीं था।",
        "in_force_stayed_omission": "सरकार ने नियम हटाया था, पर **सुप्रीम कोर्ट ने उस पर रोक** "
            "लगाई — "
        "इसलिए मामला लंबित (*विचाराधीन*) रहते नियम लागू रहा।",
        "omitted_stay_vacated": "सुप्रीम कोर्ट ने **मामला बंद कर रोक हटा दी**, इसलिए नियम हटा हुआ "
            "ही है।",
    },
    "gu": {
        "in_force": "નિયમ કાયદાનો ભાગ હતો અને **લાગુ** હતો.",
        "omitted": "સરકારી જાહેરનામાથી નિયમ **દૂર કરાયો** હતો, તેથી લાગુ ન હતો.",
        "in_force_stayed_omission": "સરકારે નિયમ દૂર કર્યો, પણ **સુપ્રીમ કોર્ટે તેના પર રોક** મૂકી "
            "— "
        "તેથી કેસ બાકી (*વિચારાધીન*) હતો ત્યારે નિયમ લાગુ રહ્યો.",
        "omitted_stay_vacated": "સુપ્રીમ કોર્ટે **કેસ બંધ કરી રોક હટાવી**, તેથી નિયમ દૂર જ રહે છે.",
    },
}
STATUS_SHORT = {
    "in_force": "in force",
    "omitted": "omitted",
    "in_force_stayed_omission": "omitted, but omission stayed by the Supreme Court",
    "omitted_stay_vacated": "omitted, stay vacated",
}

# App vocabulary (plain words; restates the UI, no legal facts). Mirrors web/src/explain.ts.
APP_TERMS = {
    "sub judice": "Latin for “under judgment”: a court case about the matter is still pending.",
    "stay": "A court order that temporarily pauses something. Here the Supreme Court paused the "
    "deletion of Rule 170, so the rule kept applying for a while.",
    "vacated": "The court cancelled its own earlier pause order, so the deletion took effect "
    "again.",
    "omitted": "Deleted from the law book through an official notification.",
    "in force": "The rule applies on that date.",
    "gazette": "The Gazette of India is the government's official publication where rule changes "
    "are printed. A G.S.R. number identifies one such notification.",
    "jurisdiction": "Whose law you are asking about: IN = India, US = United States, EU = European "
    "Union, WIPO-track = the global treaty process.",
    "as-of": "The date your question is about. Laws change, so I answer with the law that applied "
    "on that date — not just today's.",
    "rag": "Retrieval-Augmented Generation: first search a library of real documents, then answer "
    "only from what was found.",
    "static rag": "An ordinary RAG chatbot with no idea of dates — it can quote a rule that was "
    "already deleted on your date.",
    "abstain": "Refusing to answer when no official source supports an answer. I do it on purpose.",
    "abs": "Access & Benefit Sharing: companies that commercially use India's biological resources "
    "share part of their earnings with the communities that conserved them. Ask me to "
    "calculate it.",
    "passport": "A one-page checklist of the rules for your product type on your chosen date, each "
    "with its legal source.",
    "tkdl": "The Traditional Knowledge Digital Library (CSIR) — a pointer only: public access is "
    "limited, and I never claim to query it.",
    "claim sentry": "My ad/label scanner: it highlights risky wording and shows the exact DMR Act "
    "provision. It flags, it never rewrites.",
    "status ledger": "My dated timeline of a law's status, where every change cites a gazette "
    "notification or court order.",
}

# ---------------------------------------------------------------- intent patterns
LEGAL = re.compile(
    r"patent|trade ?mark|copyright|licen[cs]|\blaw\b|legal|\brules?\b|\bact\b|section|regulat|"
    r"advertis|\badvert|\bads?\b|gst|\btax|\bfee|court|gazette|\bban|allowed|permit|illegal|comply|"
    r"complian|\babs\b|benefit.?shar|biodivers|tkdl|\bgi\b|geographical indication|export|import|"
    r"fda|fssai|\blabel|registr|prohibit|obligat|ip rights|intellectual|stay|omitted|in force|"
    r"कानून|नियम|पेटेंट|विज्ञापन|लाइसेंस|अधिनियम|કાયદો|નિયમ|જાહેરાત|પેટન્ટ|લાયસન્સ",
    re.I,
)
GREETING = re.compile(
    r"^\s*(hi+|hello|hey|hola|namaste|namaskar|good (morning|afternoon|evening)|"
    r"नमस्ते|नमस्कार|નમસ્તે|નમસ્કાર|kem cho|કેમ છો)\b",
    re.I,
)
THANKS = re.compile(r"\b(thank|thanks|thx|dhanyavad|shukriya)\b|धन्यवाद|शुक्रिया|આભાર", re.I)
HELP = re.compile(
    r"what can you do|\bhelp\b|capabilit|features|how (do i|to) use|who are you|"
    r"what are you|about (you|this app)|your tools|what do you do|मदद|તમે શું",
    re.I,
)
TIMELINE = re.compile(
    r"timeline|history|chronolog|over time|all (the )?dates|how (has|did) .* chang|"
    r"when did .* chang|इतिहास|समयरेखा|ઇતિહાસ",
    re.I,
)
ABS = re.compile(
    r"benefit[- ]?shar|\babs\b|access and benefit|royalt|biological resource|"
    r"how much .*(pay|share)|लाभ.?साझा|લાભ",
    re.I,
)
PASSPORT = re.compile(
    r"passport|checklist|check list|what rules apply|obligations|compliance (for|of)|"
    r"need an? (manufactur\w* )?licen[cs]e|licen[cs]e (for|to make|to manufacture)|"
    r"पासपोर्ट|चेकलिस्ट|પાસપોર્ટ",
    re.I,
)
CLAIM = re.compile(
    r"(check|scan|review|audit|is this|flag|analy[sz]e).{0,25}\b(ad|ads|advert\w*|claim|"
    r"label|tagline|slogan|copy|packag\w*|banner|post)\b|claim sentry|^/check",
    re.I,
)
COMPARE = re.compile(
    r"compare|static rag|ordinary (chat)?bot|normal (chat)?bot|chatgpt|other chatbots?|"
    r"without (the )?date|तुलना|સરખામણી",
    re.I,
)
LIBRARY = re.compile(
    r"(which|what|list|show)( all)? (your )?(documents|sources|docs|library|corpus)|"
    r"your (library|sources|corpus)|what do you know about the law",
    re.I,
)
DEFINE = re.compile(
    r"^\s*(what is|what's|whats|what does|define|meaning of|explain|what are)\s+"
    r"(an? |the )?(.+?)(\s+mean)?\s*\??\s*$",
    re.I,
)
MEDICAL = re.compile(
    r"\b(dose|dosage|how much should i take|should i take|what should i take|"
    r"i have|i am suffering|cure my|treat my|my (mother|father|child|son|daughter) has|"
    r"prescri)",
    re.I,
)
JUR = [
    ("US", re.compile(r"\b(US|U\.S\.?|USA|united states|america|fda)\b", re.I)),
    ("EU", re.compile(r"\b(EU|europe|european)\b", re.I)),
    ("WIPO-track", re.compile(r"\b(wipo|gratk|treaty|international)\b", re.I)),
    ("IN", re.compile(r"\b(india|indian|भारत|ભારત)\b", re.I)),
]
CATEGORIES = {
    "classical": re.compile(r"classical|shastr|शास्त्र|શાસ્ત્ર", re.I),
    "proprietary": re.compile(r"proprietary|own formula|patent or proprietary", re.I),
    "phytopharma": re.compile(r"phyto", re.I),
}
_AMOUNT = re.compile(
    r"(?:₹|rs\.?|inr)?\s*([\d,]+(?:\.\d+)?)\s*(crores?|cr\b|lakhs?|lacs?|lakh|"
    r"million|mn\b|billion|करोड़|करोड|लाख|કરોડ|લાખ)?",
    re.I,
)


def parse_amount(text: str) -> int | None:
    best = None
    for m in _AMOUNT.finditer(text):
        raw, unit = m.group(1).replace(",", ""), (m.group(2) or "").lower()
        if not raw or raw == ".":
            continue
        try:
            n = float(raw)
        except ValueError:
            continue
        if re.match(r"(19|20)\d\d$", raw) and not unit:
            continue  # a year, not money
        mult = (
            CRORE
            if unit.startswith(("cr", "करो", "કરો"))
            else LAKH
            if unit.startswith(("la", "लाख", "લાખ"))
            else 1_000_000
            if unit.startswith(("mi", "mn"))
            else 1_000_000_000
            if unit.startswith("bi")
            else 1
        )
        if mult == 1 and n < 1000:
            continue  # a bare small number is not a turnover
        best = int(n * mult)
    return best


def money(n: int) -> str:
    if n >= CRORE:
        return f"₹{n / CRORE:,.2f}".rstrip("0").rstrip(".") + " crore"
    if n >= LAKH:
        return f"₹{n / LAKH:,.2f}".rstrip("0").rstrip(".") + " lakh"
    return f"₹{n:,}"


@lru_cache(maxsize=1)
def knowledge() -> list[dict]:
    return yaml.safe_load(KNOWLEDGE_PATH.read_text(encoding="utf-8"))


def _words(text: str) -> list[str]:
    return re.findall(r"[\w\u0900-\u0aff]+", text.lower())


def find_knowledge(text: str) -> dict | None:
    words = _words(text)
    best, score = None, 0
    for e in knowledge():
        for group in e["keys"]:
            if all(any(w.startswith(k) for w in words) for k in group):
                s = len(group) * 10 + sum(len(k) for k in group)
                if s > score:
                    best, score = e, s
    return best


def _t(lang: str, key: str, **kw) -> str:
    return T.get(lang, T["en"]).get(key, T["en"][key]).format(**kw)


def human(d: str | dt.date) -> str:
    d = dt.date.fromisoformat(d) if isinstance(d, str) else d
    return d.strftime("%-d %b %Y")


class Trace:
    def __init__(self) -> None:
        self.steps: list[dict] = []
        self._t = time.perf_counter()

    def add(self, tool: str, detail: str) -> None:
        now = time.perf_counter()
        self.steps.append({"tool": tool, "detail": detail, "ms": round((now - self._t) * 1000, 1)})
        self._t = now


# ---------------------------------------------------------------- tools
def _legal(q: str, jur: str, day: dt.date, lang: str, ctx: dict, tr: Trace) -> dict:
    a = answer(q, jur, day).to_dict()
    # Optional LLM layer (M7), same contract as /ask: organises cited quotes, never replaces them.
    a["synthesis"] = synthesize(a, q)
    if a.get("status"):
        tr.add(
            "The Status Ledger",
            f"{a['status']['instrument']} → {a['status']['status'] or 'no entry'}",
        )
    tr.add("The Retriever", f"{a['retrieval']} · filter-before-rank on {jur} + {day.isoformat()}")
    tr.add(
        "The Answer Contract",
        "abstained"
        if a["abstain"]
        else f"{len(a['quotes'])} verbatim quote(s) · confidence {a['confidence']}",
    )
    blocks: list[dict] = []
    lines: list[str] = []
    if a["abstain"]:
        lines.append(_t(lang, "abstain", jur=jur, date=human(day)))
    else:
        st = a.get("status") or {}
        if st.get("status"):
            plain = PLAIN_STATUS.get(lang, PLAIN_STATUS["en"]).get(
                st["status"], st.get("summary", "")
            )
            lines.append(_t(lang, "status", date=human(day), inst=st["instrument"], plain=plain))
            prev = ctx.get("last_status")
            if (
                prev
                and ctx.get("last_as_of")
                and ctx.get("last_instrument") == st["instrument"]
                and ctx["last_as_of"] != day.isoformat()
            ):
                a_, b_ = human(ctx["last_as_of"]), human(day)
                if prev != st["status"]:
                    lines.append(
                        _t(
                            lang,
                            "changed",
                            a=a_,
                            b=b_,
                            s1=STATUS_SHORT.get(prev, prev),
                            s2=STATUS_SHORT.get(st["status"], st["status"]),
                        )
                    )
                    blocks.append(
                        {
                            "type": "diff",
                            "from": {"as_of": ctx["last_as_of"], "status": prev},
                            "to": {"as_of": day.isoformat(), "status": st["status"]},
                        }
                    )
                else:
                    lines.append(_t(lang, "same", a=a_))
        overlay = [
            x["text"]
            for x in a["quotes"]
            if x["role"] == "overlay" and x["chunk_id"].endswith("0026")
        ]
        if overlay:
            lines.append(_t(lang, "overlay", diseases=", ".join(overlay)))
        if not st.get("status"):
            lines.append(_t(lang, "found", n=len(a["quotes"]), jur=jur, date=human(day)))
        lines.append(_t(lang, "quotes"))
    blocks.insert(0, {"type": "answer", "answer": a})
    new_ctx = {
        **ctx,
        "last_question": q,
        "last_as_of": day.isoformat(),
        "last_jur": jur,
        "last_status": (a.get("status") or {}).get("status"),
        "last_instrument": (a.get("status") or {}).get("instrument"),
        "pending": None,
    }
    sugg = []
    if a.get("status"):
        seg_dates = ["2024-06-30", "2024-07-02", "2024-08-28", "2025-08-12"]
        sugg += [f"What about {human(d)}?" for d in seg_dates if d != day.isoformat()][:2]
        sugg += ["Show the timeline of Rule 170", "Compare with an ordinary chatbot"]
    elif a["abstain"]:
        sugg += [
            "Is Rule 170 in force?",
            "What documents do you have?",
            "Show the timeline of Rule 170",
        ]
    else:
        sugg += ["Compare with an ordinary chatbot", "What documents do you have?"]
    return {
        "intent": "legal",
        "text": "\n\n".join(lines),
        "blocks": blocks,
        "suggestions": sugg,
        "context": new_ctx,
        "audit": a,
    }


def _timeline(lang: str, day: dt.date, tr: Trace) -> dict:
    entry = ledger.load_all()[0]
    res = ledger.resolve_entry(entry, day)
    chunks = ledger.load_chunks()
    segs = []
    for seg in entry.timeline:
        segs.append(
            {
                "from": seg.start.isoformat(),
                "to": seg.end and seg.end.isoformat(),
                "status": seg.status,
                "sub_judice": seg.sub_judice,
                "summary": seg.summary,
                "current": seg.covers(day) if hasattr(seg, "covers") else False,
                "evidence": [
                    {
                        "ref": e.ref,
                        "quote": e.quote,
                        "chunk_id": e.chunk_id,
                        "source_url": e.source_url,
                        "doc_title": chunks[e.chunk_id]["doc_title"],
                    }
                    for e in seg.evidence
                ],
            }
        )
    tr.add(
        "The Status Ledger",
        f"{entry.instrument}: {len(segs)} dated segments, each gazette/court-cited",
    )
    return {
        "intent": "timeline",
        "text": _t(lang, "timeline", inst=entry.instrument),
        "blocks": [
            {
                "type": "timeline",
                "instrument": entry.instrument,
                "as_of": day.isoformat(),
                "current_status": res.status,
                "segments": segs,
            }
        ],
        "suggestions": [
            "Is Rule 170 in force?",
            "Can I advertise a classical Ayurveda medicine for diabetes?",
        ],
    }


def _abs(amount: int, day: dt.date, lang: str, text: str, tr: Trace) -> dict:
    r = abs_calc.compute(
        amount, day, None, bool(re.search(r"high.?value|rare|endanger", text, re.I))
    )
    tr.add(
        "The Passport Compiler",
        f"ABS calculator · turnover {money(amount)} · as of {day.isoformat()}",
    )
    if r.get("abstain"):
        msg = _t(lang, "abs_abstain", date=human(day))
    else:
        msg = _t(
            lang,
            "abs",
            amt=money(amount),
            date=human(day),
            slab=r["slab"]["label"],
            rate=r["slab"]["rate_pct"],
        )
    return {
        "intent": "abs",
        "text": msg,
        "blocks": [{"type": "abs", "result": r}],
        "suggestions": [
            "What about ₹40 crore?",
            "What about ₹150 crore?",
            "Explain ABS in simple words",
        ],
    }


def _passport(cat: str, day: dt.date, lang: str, tr: Trace) -> dict:
    p = passport_cat.compile_passport(cat, day)
    tr.add(
        "The Passport Compiler",
        f"{cat} passport · {len(p.get('rules', []))} rules · as of {day.isoformat()}",
    )
    msg = (
        _t(lang, "pp", title=p.get("title", cat), date=human(day), n=len(p.get("rules", [])))
        if not p.get("abstain")
        else p.get("reason", "") or _t(lang, "abstain", jur="IN", date=human(day))
    )
    others = [c for c in passport_cat.CATEGORIES if c != cat]
    return {
        "intent": "passport",
        "text": msg,
        "blocks": [{"type": "passport", "result": p}],
        "suggestions": [f"Passport for a {c} product" for c in others]
        + ["Passport as of 1 Jan 2020"],
    }


def _claims(text: str, lang: str, day: dt.date, tr: Trace) -> dict:
    s = sentry.scan(text)
    tr.add(
        "The Claim Sentry",
        f"{s['count']} risk indicator(s) · DMR Act 1954 s.3, s.4, s.5 + Schedule",
    )
    res = ledger.resolve_entry(ledger.load_all()[0], day)
    s["rule170"] = {
        "as_of": day.isoformat(),
        "status": res.status,
        "status_line": res.status_line(),
    }
    tr.add("The Status Ledger", f"Rule 170 on {day.isoformat()} → {res.status}")
    msg = _t(lang, "claim", n=s["count"]) if s["count"] else _t(lang, "claim_none")
    return {
        "intent": "claim",
        "text": msg,
        "blocks": [{"type": "claims", "result": s}],
        "suggestions": [
            'Check this ad: "Our herbal tonic is a 100% guaranteed miracle cure for '
            'joint pain and high blood pressure"',
            "Can I advertise a classical Ayurveda medicine for diabetes?",
        ],
    }


def _compare(q: str, jur: str, day: dt.date, lang: str, ctx: dict, tr: Trace) -> dict:
    ours = _legal(q, jur, day, lang, ctx, Trace())
    terms = list(dict.fromkeys(tokenize(q)))
    base = [
        {
            # The chat card renders `quote` (the Cite shape); `text` kept for API callers.
            "quote": (span := best_span(c["text"], terms)),
            "text": span,
            "chunk_id": c["chunk_id"],
            "doc_title": c["doc_title"],
            "section": c["section"],
            "source_url": c["source_url"],
        }
        for c in static_retrieve(q, jur)
    ]
    tr.add("Static RAG baseline", f"{len(base)} passage(s) · no date, no ledger")
    tr.add(
        "The Answer Contract",
        f"{'abstained' if ours['audit']['abstain'] else 'answered'} as of {day.isoformat()}",
    )
    return {
        "intent": "compare",
        "text": _t(lang, "compare"),
        "blocks": [{"type": "compare", "question": q, "ours": ours["audit"], "baseline": base}],
        "suggestions": ["What about 2 Jul 2024?", "Show the timeline of Rule 170"],
        "context": ours["context"],
        "audit": ours["audit"],
    }


def _library(lang: str, tr: Trace) -> dict:
    docs: dict[str, dict] = {}
    for c in default_index().chunks:
        d = docs.setdefault(
            c["doc_id"],
            {
                "doc_id": c["doc_id"],
                "title": c["doc_title"],
                "jurisdiction": c.get("jurisdiction"),
                "url": c["source_url"],
                "chunks": 0,
            },
        )
        d["chunks"] += 1
    n = sum(d["chunks"] for d in docs.values())
    ver = default_index().corpus_version
    tr.add("The Library", f"{len(docs)} documents · {n} chunks")
    return {
        "intent": "library",
        "text": _t(lang, "library", docs=len(docs), chunks=n, ver=ver[:19] + "…"),
        "blocks": [
            {
                "type": "library",
                "docs": sorted(
                    docs.values(),
                    key=lambda d: (d["jurisdiction"] != "IN", d["jurisdiction"] or "", d["title"]),
                ),
            }
        ],
        "suggestions": [
            "Does the US FDA warn about heavy metals in Ayurvedic products?",
            "What is Ayurveda Aahara?",
            "What does the WIPO GRATK treaty say about disclosure?",
        ],
    }


def _help(lang: str) -> dict:
    return {
        "intent": "help",
        "text": _t(lang, "hello"),
        "blocks": [{"type": "capabilities"}],
        "suggestions": [
            "Is Rule 170 in force?",
            "Calculate my ABS benefit share",
            'Check this ad: "Cures diabetes in 30 days, 100% guaranteed"',
            "What are the three doshas?",
        ],
    }


def _general(q: str, lang: str, history: list[dict], tr: Trace, legal_missed: bool = False) -> dict:
    kb = find_knowledge(q)
    blocks: list[dict] = []
    if MEDICAL.search(q):
        blocks.append({"type": "safety", "text": _t(lang, "medical")})
        tr.add("Safety guard", "health question → no treatment or dose advice")
    if kb:
        tr.add("Curated knowledge", f"matched '{kb['title']}' (offline)")
    gen = llm.ask(q, history, kb["text"] if kb else None)
    if gen:
        tr.add("General LLM", f"{gen['provider']} · {gen['source']} · legal sentences scrubbed")
        text = gen["text"]
        blocks.append(
            {
                "type": "knowledge",
                "title": kb["title"] if kb else None,
                "label": _t(lang, "bg_label"),
                "more": kb.get("more") if kb else None,
                "provider": gen["provider"],
                "source": gen["source"],
            }
        )
    elif kb:
        text = kb["text"].strip()
        blocks.append(
            {
                "type": "knowledge",
                "title": kb["title"],
                "label": _t(lang, "bg_label"),
                "more": kb.get("more"),
                "provider": "curated",
                "source": "offline",
            }
        )
    else:
        tr.add("Curated knowledge", "no match; no LLM configured → no guess")
        return {
            "intent": "unknown",
            "text": _t(lang, "general_none"),
            "blocks": blocks,
            "suggestions": [
                "What are the three doshas?",
                "What is Panchakarma?",
                "Is Rule 170 in force?",
                "What can you do?",
            ],
        }
    related = {
        "doshas": ["What is Prakriti?", "What are the six tastes?"],
        "ashwagandha": ["What is Rasayana?", "Is Ayurveda safe?"],
        "turmeric": ["What is TKDL?", "What is neem used for?"],
    }.get(kb["id"] if kb else "", [])
    return {
        "intent": "general",
        "text": text,
        "blocks": blocks,
        "suggestions": related
        + [
            "What are the three doshas?",
            "What is Panchakarma?",
            "Can I advertise a classical Ayurveda medicine for diabetes?",
        ][: 4 - len(related)],
    }


def _define(q: str) -> str | None:
    m = DEFINE.match(q)
    if not m:
        return None
    term = m.group(3).lower().strip(" ?.")
    for k in sorted(APP_TERMS, key=len, reverse=True):
        if (
            term == k
            or term.startswith(k + " ")
            or term.replace("-", " ") == k.replace("-", " ")
            or term in (k + "s", "a " + k)
        ):
            return k
    return None


# ---------------------------------------------------------------- the router
def reply(
    message: str,
    jurisdiction: str = "IN",
    as_of: dt.date | None = None,
    lang: str = "en",
    context: dict | None = None,
    history: list[dict] | None = None,
) -> dict:
    ctx = dict(context or {})
    history = history or []
    lang = lang if lang in T else "en"
    day = as_of or dt.date.today()
    jur = jurisdiction
    tr = Trace()
    msg = message.strip()
    notes: list[str] = []

    # 1. The Two Switches, spoken: a date or jurisdiction inside the message moves the switch.
    found, rest, assumption = find_date(msg)
    if found:
        if found != day:
            notes.append(
                _t(
                    lang,
                    "switched_date",
                    date=human(found),
                    note=_t(lang, assumption) if assumption else "",
                )
            )
        day = found
        tr.add("The Two Switches", f"as-of date from your words → {day.isoformat()}")
    for code, rx in JUR:
        if rx.search(rest) and not (code == "IN" and jur == "IN"):
            if code != jur:
                jur = code
                notes.append(_t(lang, "switched_jur", jur=code))
                tr.add("The Two Switches", f"jurisdiction from your words → {code}")
            break

    out = _route(msg, rest, bool(found), jur, day, lang, ctx, history, tr)
    out["text"] = "\n\n".join([*notes, out["text"]]) if notes else out["text"]
    out.setdefault(
        "context", {**ctx, "pending": ctx.get("pending") if out["intent"] in ("ask",) else None}
    )
    out["as_of"] = day.isoformat()
    out["jurisdiction"] = jur
    out["trace"] = tr.steps
    return out


def _route(
    msg: str,
    rest: str,
    had_date: bool,
    jur: str,
    day: dt.date,
    lang: str,
    ctx: dict,
    history: list[dict],
    tr: Trace,
) -> dict:
    pending = ctx.get("pending")
    low = msg.lower()
    # 2. Answers to a question I asked (back-and-forth).
    if pending == "abs_turnover" and (amt := parse_amount(msg)) is not None:
        return _abs(amt, day, lang, msg, tr)
    if pending == "passport_category":
        for cat, rx in CATEGORIES.items():
            if rx.search(msg):
                return _passport(cat, day, lang, tr)
    if pending == "claim_text" and len(msg.split()) >= 3 and not CLAIM.search(msg):
        return _claims(msg, lang, day, tr)

    # 3. Small talk.
    if GREETING.match(msg) and len(msg.split()) <= 4:
        return _help(lang)
    if THANKS.search(msg) and len(msg.split()) <= 6:
        return {
            "intent": "thanks",
            "text": _t(lang, "thanks"),
            "blocks": [],
            "suggestions": ["What about 28 Aug 2024?", "Calculate my ABS benefit share"],
        }
    if HELP.search(msg) and len(msg.split()) <= 8:
        return _help(lang)

    # 4. Tools, by intent.
    if CLAIM.search(msg) or re.match(r"^\s*/check", msg):
        body = re.split(r":|/check", msg, maxsplit=1)
        m = re.search(r"[\"“'‘](.{6,})[\"”'’]", msg)
        text = (
            m.group(1)
            if m
            else (body[1].strip() if len(body) > 1 and len(body[1].split()) >= 3 else "")
        )
        if text:
            return _claims(text, lang, day, tr)
        return {
            "intent": "ask",
            "text": _t(lang, "claim_ask"),
            "blocks": [],
            "suggestions": [
                '"Cures diabetes in 30 days, 100% guaranteed, no side effects"',
                '"A miracle herbal tonic for strong immunity"',
            ],
            "context": {**ctx, "pending": "claim_text"},
        }
    if ABS.search(msg) or (pending == "abs_turnover" and parse_amount(msg)):
        amt = parse_amount(msg)
        if amt is not None:
            return _abs(amt, day, lang, msg, tr)
        # "what is ABS?" wants the glossary; "what is *my* ABS share?" wants the calculator.
        if re.search(r"explain|what is|simple|meaning|मतलब|એટલે", low) and not re.search(
            r"\bmy\b|\bour\b|calculat|comput|how much|मेरा|मेरी|અમારો|મારો", low
        ):
            return {
                "intent": "define",
                "text": f"**ABS** — {APP_TERMS['abs']}",
                "blocks": [],
                "suggestions": ["Calculate my ABS benefit share", "What about ₹40 crore?"],
            }
        return {
            "intent": "ask",
            "text": _t(lang, "abs_ask"),
            "blocks": [],
            "suggestions": ["₹3 crore", "₹40 crore", "₹150 crore"],
            "context": {**ctx, "pending": "abs_turnover"},
        }
    if PASSPORT.search(msg):
        for cat, rx in CATEGORIES.items():
            if rx.search(msg):
                return _passport(cat, day, lang, tr)
        return {
            "intent": "ask",
            "text": _t(lang, "pp_ask"),
            "blocks": [],
            "suggestions": ["Classical", "Proprietary", "Phytopharmaceutical"],
            "context": {**ctx, "pending": "passport_category"},
        }
    if TIMELINE.search(msg):
        return _timeline(lang, day, tr)
    if COMPARE.search(msg):
        q = ctx.get("last_question")
        if not q:
            return {
                "intent": "compare",
                "text": _t(lang, "compare_none"),
                "blocks": [],
                "suggestions": ["Is Rule 170 in force?"],
            }
        return _compare(q, jur, day, lang, ctx, tr)
    if LIBRARY.search(msg):
        return _library(lang, tr)
    term = _define(msg)
    if term:
        tr.add("The Glossary (app terms)", term)
        return {
            "intent": "define",
            "text": f"**{term.title() if len(term) > 3 else term.upper()}** — {APP_TERMS[term]}",
            "blocks": [],
            "suggestions": ["Is Rule 170 in force?", "Show the timeline of Rule 170"],
        }

    # 5. A bare date (or jurisdiction) = re-ask the previous question on the new switches.
    rest_no_jur = rest
    for _, rx in JUR:
        rest_no_jur = rx.sub(" ", rest_no_jur)
    if (had_date or rest_no_jur != rest) and is_follow_up(rest_no_jur):
        if ctx.get("last_question"):
            tr.add("The Conversation", "follow-up → re-asking your previous question")
            return _legal(ctx["last_question"], jur, day, lang, ctx, tr)
        return {
            "intent": "date",
            "text": _t(lang, "date_only", date=human(day)),
            "blocks": [],
            "suggestions": [
                "Is Rule 170 in force?",
                "Can I advertise a classical Ayurveda medicine for diabetes?",
            ],
        }

    # 6. Legal vs general.
    q = rest if had_date and rest else msg
    legalish = bool(LEGAL.search(q))
    if not legalish and find_knowledge(q):
        return _general(q, lang, history, tr)
    out = _legal(q, jur, day, lang, ctx, tr)
    a = out["audit"]
    if a["abstain"] and not legalish:
        tr.add("The Conversation", "not a legal question → general knowledge path")
        return _general(q, lang, history, tr)
    return out
