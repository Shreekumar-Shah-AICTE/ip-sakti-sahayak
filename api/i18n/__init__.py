"""The Glossary: offline, keyless hi/gu -> en query translation for The Answer Contract.

Why: The Library is English and the lexical coverage gate tokenises [a-z0-9] only, so every
Hindi/Gujarati question scored 0 coverage and abstained (DECISIONS D-014: no safe MIN_COSINE).
This module maps each *content word* of a hi/gu question to its English statutory term from a
small hand-curated glossary. It is conservative by construction:

- A content word the glossary does not know is kept as an **unknown term** that can never
  match an English chunk, so it still counts in the coverage denominator. A partial
  translation therefore makes admission *harder*, never easier.
- Only function words (postpositions, auxiliaries, question words) are dropped.
- Every entry must be motivated by an answerable (L) eval item; no entry may exist to make a
  must-abstain (D) item answer (same rule as TERM_MAP, DECISIONS D-013). Domain words that
  only appear in D items (GST, trademark, fee, SIPP, bitcoin ...) are deliberately absent.
- The translations are the agent's own; a native-speaker check is an Operator task before any
  multilingual figure is quoted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from api.retriever import tokenize

DEVANAGARI = re.compile(r"[\u0900-\u097F]")
GUJARATI = re.compile(r"[\u0A80-\u0AFF]")

# Function words only. Adding a content word here would silently raise coverage — don't.
STOP = {
    "hi": set("""क्या है हैं में की का के को पर से और तक किन कौन कौनसे कितना कितनी कितने करने
        कराया जा सकता सकती सकते होगी होगा होगे देनी किया किसी लिए ने यह वह भी अभी हो""".split()),
    "gu": set("""શું છે માં ની નો ના નું ને પર અને કઈ કયા કયો કોણે કેટલી કેટલો કેટલું થઈ શકે
        થાય ચૂકવવાની અંગે માટે હજી એ""".split()),
}

# Gujarati writes case markers as suffixes: ટીકેડીએલની = TKDL + ની, ઉત્પાદનોમાં = ઉત્પાદન + ોમાં.
# Stripped only when the
# remaining stem is a glossary headword, so an unknown word stays whole.
# Plural is the matra ો after a consonant (ઉત્પાદનો) but the vowel ઓ after a vowel (કચેરીઓ).
GU_SUFFIXES = ("ોમાં", "ોને", "ોની", "ોનો", "ઓમાં", "ઓને", "ઓની", "ઓનો", "ઓ",
               "માં", "ની", "નો", "ના", "નું", "ને", "થી", "ો")

# (lang, phrase) -> English. Multi-word phrases are matched longest-first. Motivating eval
# items in the comment after each group (eval/sets/multilingual.yaml).
GLOSSARY: dict[str, dict[str, str]] = {
    "hi": {
        "संहिताबद्ध": "codified", "पारंपरिक": "traditional", "ज्ञान": "knowledge",  # HL01
        "वार्षिक": "annual", "टर्नओवर": "turnover", "लाभ साझा": "benefit sharing",
        "लाभ": "benefit", "राशि": "amount",  # HL02
        "पेटेंट": "patent", "कार्यालयों": "offices", "कार्यालय": "office",
        "टीकेडीएल": "tkdl", "पहुंच": "access",  # HL03
        "औषधि": "drugs", "चमत्कारिक": "magic", "उपचार": "remedies", "अधिनियम": "act",
        "अनुसूची": "schedule", "रोग": "diseases", "सूचीबद्ध": "listed",  # HL04
        "भारत": "india", "आयुर्वेदिक": "ayurvedic", "दवा": "medicine",
        # "पेटेंट कराया (जा सकता)" = "can be patented": the verb phrase is "patentable", not the
        # noun "patent" -- the noun collides with the Drugs Rules' "patent or proprietary
        # medicine" (D-013). Mapping the phrase routes it through TERM_MAP like English L06.
        "पेटेंट कराया": "patentable",  # HL05
        "आयुर्वेद": "ayurveda", "आहार": "aahara", "लेबल": "label", "ठीक करने": "cure",
        "दावा": "claim",  # HL06
        "उत्पादों": "products", "उत्पाद": "product", "भारी": "heavy", "धातुओं": "metals",
        "एफडीए": "fda", "चेतावनी": "warning",  # HL07
        "हर्बल": "herbal", "औषधीय": "medicinal", "सरलीकृत": "simplified",
        "पंजीकरण": "registration", "प्रक्रिया": "procedure",  # HL08
    },
    "gu": {
        "સંહિતાબદ્ધ": "codified", "પરંપરાગત": "traditional", "જ્ઞાન": "knowledge",  # GL01
        "વાર્ષિક": "annual", "ટર્નઓવર": "turnover", "લાભ વહેંચણી": "benefit sharing",
        "લાભ": "benefit", "રકમ": "amount",  # GL02
        "પેટન્ટ": "patent", "કચેરી": "office", "ટીકેડીએલ": "tkdl", "ઍક્સેસ": "access",  # GL03
        "ડ્રગ્સ": "drugs", "મેજિક": "magic", "રેમેડીઝ": "remedies", "અધિનિયમ": "act",
        "અનુસૂચિ": "schedule", "રોગ": "diseases", "સૂચિબદ્ધ": "listed",  # GL04
        "ભારત": "india", "આયુર્વેદિક": "ayurvedic", "દવા": "medicine",
        "પેટન્ટ થઈ": "patentable",  # GL05 (see HL05 note)
        "ઉત્પાદન": "products", "ભારે": "heavy", "ધાતુ": "metals", "એફડીએ": "fda",
        "ચેતવણી": "warning",  # GL06
    },
}
# "એન્ડ" (and) is a transliterated function word inside the DMR Act's Gujarati name.
STOP["gu"].add("એન્ડ")

_PUNCT = re.compile(r"[?？!।,.:;\"'()\[\]]")


def detect(text: str) -> str:
    """'hi' for Devanagari, 'gu' for Gujarati script, else 'en'."""
    if GUJARATI.search(text):
        return "gu"
    if DEVANAGARI.search(text):
        return "hi"
    return "en"


@dataclass(frozen=True)
class Translation:
    lang: str
    english: str  # the translated content words, space-joined (for dense + display)
    terms: list[str] = field(default_factory=list)  # coverage/scoring terms, unknowns kept
    unknown: list[str] = field(default_factory=list)


def _lookup(lang: str, word: str) -> str | None:
    g = GLOSSARY[lang]
    if word in g:
        return g[word]
    if lang == "gu":
        for suf in GU_SUFFIXES:
            if word.endswith(suf) and word[: -len(suf)] in g:
                return g[word[: -len(suf)]]
    return None


def translate(question: str) -> Translation | None:
    """Glossary translation of a hi/gu question; None for English (nothing to do)."""
    lang = detect(question)
    if lang == "en":
        return None
    words = [w for w in _PUNCT.sub(" ", question).split() if w]
    english, unknown, i = [], [], 0
    while i < len(words):
        two = " ".join(words[i:i + 2])
        if i + 1 < len(words) and (hit := _lookup(lang, two)):
            english.append(hit)
            i += 2
            continue
        w = words[i]
        i += 1
        if w in STOP[lang]:
            continue
        if (hit := _lookup(lang, w)) is not None:
            english.append(hit)
        elif re.fullmatch(r"[a-z0-9]+", w.lower()):
            english.append(w.lower())  # Latin words inside a hi/gu question pass through
        else:
            unknown.append(w)
    en = " ".join(english)
    # Unknown words stay as terms: they never match an English chunk, so they lower coverage.
    terms = list(dict.fromkeys(tokenize(en) + unknown))
    return Translation(lang, en, terms, unknown)
