"""The Claim Sentry (M11, lite) — flags risk indicators in ad / label text. Flags, never rewrites.

Every flag carries a verbatim quote from The Library (the DMR Act, 1954) that is checked
against its chunk when the module loads; a quote not found in its chunk is dropped, never
paraphrased (KERNEL 7.3, 7.7). Output is a list of *risk indicators* for a human to judge,
never a verdict on the ad.
"""

from __future__ import annotations

import re
from functools import lru_cache

from api import ledger

S3 = "in-dmr-act-1954#0008"
S4 = "in-dmr-act-1954#0010"
S5 = "in-dmr-act-1954#0011"
SCHED_A, SCHED_B = "in-dmr-act-1954#0026", "in-dmr-act-1954#0027"

# (id, trigger stems/regex, chunk, verbatim quote, why-it-matters in plain words)
_RULES = [
    (
        "s3a",
        r"miscarriage|abortion|contracepti|prevent(?:s|ion of)? (?:conception|pregnancy)|"
        r"गर्भपात|ગર્ભપાત",
        S3,
        "the procurement of miscarriage in women or prevention of conception in women",
        "Section 3(a) of the DMR Act lists this purpose among prohibited advertisement claims.",
    ),
    (
        "s3b",
        r"sex(?:ual)? (?:power|pleasure|stamina|performance)|virility|libido|stamina in bed|"
        r"मर्दाना|यौन शक्ति|જાતીય",
        S3,
        "the maintenance or improvement of the capacity of human beings for sexual pleasure",
        "Section 3(b) lists this purpose among prohibited advertisement claims.",
    ),
    (
        "s3c",
        r"menstrua|irregular periods|period pain|मासिक|માસિક",
        S3,
        "the correction of menstrual disorder in women",
        "Section 3(c) lists this purpose among prohibited advertisement claims.",
    ),
    (
        "s4",
        r"\b100 ?%|guarantee|permanent(?:ly)? cure|cures? (?:all|every|in \d+)|no side[- ]effects?|"
        r"instant(?:ly)? (?:cure|relief|result)|clinically proven|doctor[s]? recommend|"
        r"गारंटी|स्थायी इलाज|ગેરંટી|કાયમી",
        S4,
        "makes a false claim for the drug",
        "Absolute or unverifiable wording can be a false or misleading claim under section 4 — "
        "whether it actually is turns on the evidence behind it, so a human must judge.",
    ),
    (
        "s5",
        r"magic|miracle|chamatkar|चमत्कार|जादू|ચમત્કાર|જાદુ|talisman|mantra|kavach",
        S5,
        "No person carrying on or purporting to carry on the profession of administering magic "
        "remedies shall take any part in the publication of any advertisement referring to any "
        "magic remedy",
        "Words like 'magic' or 'miracle' can bring section 5 (magic remedies) into view.",
    ),
]

# Schedule diseases: question stem (en/hi/gu) -> verbatim Schedule entry.
_DISEASES = {
    r"appendic": "1. Appendicitis.",
    r"arterioscler": "2. Arteriosclerosis.",
    r"blind": "3. Blindness",
    r"blood poison|sepsis": "4. Blood poisoning.",
    r"cancer|कैंसर|કેન્સર": "6. Cancer",
    r"tumou?r": "51. Tumours.",
    r"cataract|मोतियाबिंद": "7. Cataract.",
    r"deaf|बहरा": "8. Deafness.",
    r"diabet|blood sugar|sugar (?:control|level)|मधुमेह|डायबिटीज|ડાયાબિટીસ|મધુમેહ": "9. Diabetes.",
    r"epilep|मिर्गी": "17. Epilepsy.",
    r"fever|बुखार|તાવ": "19. Fevers (in general).",
    r"kidney stone|gall ?stone|bladder stone|पथरी|પથરી": "22. Gall stones, kidney stones and "
        "bladder stones.",
    r"glaucoma": "24. Glaucoma.",
    r"goitre|goiter": "25. Goitre.",
    r"heart|cardiac|हृदय|दिल|હૃદય": "26. Heart diseases.",
    r"blood pressure|hypertension|\bbp\b|रक्तचाप|બ્લડ પ્રેશર": "27. High or low blood pressure.",
    r"leprosy|कुष्ठ": "32. Leprosy.",
    r"leucoderma|vitiligo|सफेद दाग": "33. Leucoderma.",
    r"obes|weight loss|fat loss|मोटापा|વજન": "38. Obsesity.",
    r"paralys|लकवा": "39. Paralysis.",
    r"pneumonia": "42. Pneumonia.",
    r"rheumat|arthrit|joint pain|गठिया|સંધિવા": "43. Rheumatism.",
    r"impoten|erectile|नपुंसक": "45. Sexual impotence.",
    r"tubercul|\btb\b|टीबी|क्षय": "50. Tuberculosis.",
    r"typhoid": "52. Typhoid fever.",
    r"ulcer": "53. Ulcers of gastrointestinal tracts.",
    r"asthma|अस्थमा|દમ": None,  # not in the printed Schedule chunk we hold -> never flagged
}


@lru_cache(maxsize=1)
def _verified() -> tuple[list[tuple], dict]:
    chunks = ledger.load_chunks()
    rules = [r for r in _RULES if r[2] in chunks and r[3] in chunks[r[2]]["text"]]
    sched = {}
    for rx, entry in _DISEASES.items():
        if entry is None:
            continue
        for cid in (SCHED_A, SCHED_B):
            if cid in chunks and entry in chunks[cid]["text"]:
                sched[rx] = (cid, entry)
                break
    return rules, sched


def _cite(chunk_id: str, quote: str) -> dict:
    c = ledger.load_chunks()[chunk_id]
    return {
        "chunk_id": chunk_id,
        "quote": quote,
        "doc_title": c["doc_title"],
        "section": c["section"],
        "source_url": c["source_url"],
    }


def _whole_word(text: str, start: int, end: int) -> tuple[int, int]:
    """Grow a stem match ("diabet") out to the word the reader sees ("diabetes").

    The stems are deliberately short so inflections match; highlighting only the stem
    would look like a bug to the person whose copy is being checked.
    """
    while start > 0 and (text[start - 1].isalnum() or text[start - 1] == "-"):
        start -= 1
    while end < len(text) and (text[end].isalnum() or text[end] == "-"):
        end += 1
    return start, end


def scan(text: str) -> dict:
    """Risk indicators for an ad/label text. Spans index into the original text."""
    rules, sched = _verified()
    low = text.lower()
    flags = []
    for rx, (cid, entry) in sched.items():
        for m in re.finditer(rx, low):
            lo, hi = _whole_word(text, m.start(), m.end())
            flags.append(
                {
                    "id": "s3d",
                    "span": [lo, hi],
                    "match": text[lo:hi],
                    "title": f"Schedule disease: {entry.split('. ', 1)[1].rstrip('.')}",
                    "why": "Section 3(d) of the DMR Act prohibits advertising a drug for the "
                    "diseases in its Schedule. This wording appears to name one.",
                    "cites": [
                        _cite(
                            S3,
                            "the diagnosis, cure, mitigation, treatment or "
                            "prevention of any disease, disorder or condition "
                            "specified in the Schedule",
                        ),
                        _cite(cid, entry),
                    ],
                }
            )
            break
    for rid, rx, cid, quote, why in rules:
        m = re.search(rx, low)
        if m:
            lo, hi = _whole_word(text, m.start(), m.end())
            flags.append(
                {
                    "id": rid,
                    "span": [lo, hi],
                    "match": text[lo:hi],
                    "title": {
                        "s3a": "Conception / miscarriage claim",
                        "s3b": "Sexual-capacity claim",
                        "s3c": "Menstrual-disorder claim",
                        "s4": "Absolute or unverifiable claim",
                        "s5": "'Magic remedy' wording",
                    }[rid],
                    "why": why,
                    "cites": [_cite(cid, quote)],
                }
            )
    flags.sort(key=lambda f: f["span"][0])
    return {
        "text": text,
        "flags": flags,
        "count": len(flags),
        "note": "Risk indicators only — not a verdict. The Claim Sentry flags, it never "
        "rewrites; a regulatory professional decides.",
    }
