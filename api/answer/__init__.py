"""The Answer Contract: quotes, citations, status-as-of line, confidence, abstention.

Keyless mode is extractive: every quote is a verbatim span of a Library chunk, so the
system cannot say anything the corpus does not say. When the evidence is thin it
abstains and says why — abstention is a feature.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import asdict, dataclass, field

from api import ledger
from api.i18n import translate
from api.retriever import Index, default_index, normalize_jurisdiction, tokenize

# Share of query terms a chunk must contain. Measured, not guessed (run 04 sweep on
# eval/sets/dev.yaml, DECISIONS D-013): 0.55-0.60 is the only band that holds abstention
# accuracy at 1.0; at <=0.50 "GST rate on Ayurvedic cosmetics" (D02) gets answered.
MIN_COVERAGE = 0.6
# Dense similarity that admits a hit *without* lexical coverage (hybrid mode only).
# None = dense only re-ranks; it never lets a chunk past the gate on its own.
MIN_COSINE: float | None = None
DISCLAIMER = "Guidance with sources, not legal advice. Confirm with a qualified professional."


@dataclass
class Quote:
    text: str
    chunk_id: str
    doc_title: str
    section: str
    source_url: str
    retrieved_on: str
    role: str  # "status_evidence" | "overlay" | "retrieved"


@dataclass
class Answer:
    question_terms: list[str]
    jurisdiction: str
    as_of: str
    corpus_version: str
    abstain: bool
    reason: str = ""
    confidence: str = "none"
    status_line: str | None = None
    status: dict | None = None
    quotes: list[Quote] = field(default_factory=list)
    disclaimer: str = DISCLAIMER
    retrieval: str = "bm25"  # "bm25" (keyless core) | "hybrid" (BM25 + dense, RRF)
    # The Glossary (hi/gu -> en): {lang, english, unknown}; None for English questions.
    translation: dict | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.;:])\s+", text)
    return [p for p in parts if len(p.split()) >= 4] or [text]


def best_span(text: str, terms: list[str], max_words: int = 60) -> str:
    """The sentence with most query terms, verbatim; trimmed on a word boundary."""
    wanted = set(terms)
    best = max(_sentences(text), key=lambda s: len(wanted & set(tokenize(s))))
    words = best.split(" ")
    return " ".join(words[:max_words]) if len(words) > max_words else best


def _find_instrument(question: str, extra: str = "") -> ledger.Entry | None:
    """The ledger entry a question is about: by name first, then by topic (run 12)."""
    q = question.lower()
    entries = ledger.load_all()
    for entry in entries:
        for name in (entry.instrument, *entry.aliases):
            if re.search(r"(?<![a-z0-9])" + re.escape(name.lower()) + r"(?![a-z0-9])", q):
                return entry
    words = re.findall(r"[\w\u0900-\u0aff]+", f"{q} {extra.lower()}")
    for entry in entries:
        if entry.topics and all(any(w.startswith(stem) for w in words for stem in group)
                                for group in entry.topics):
            return entry
    return None


# The DMR Act overlay (run 12; PITCH_DEFENCE §3 closing beat). An advertisement question that
# names a Schedule disease also gets the DMR Act s.3(d) prohibition and the Schedule entry --
# whatever Rule 170's status. Quotes are verbatim and verified against the chunk at use; a
# quote not found in its chunk is dropped, never paraphrased (KERNEL 7.3).
DMR_SECTION = ("in-dmr-act-1954#0008", "the diagnosis, cure, mitigation, treatment or prevention "
               "of any disease, disorder or condition specified in the Schedule")
DMR_SCHEDULE = "in-dmr-act-1954#0026"
DMR_DISEASES = {  # question stem (en/hi/gu) -> verbatim Schedule entry
    "diabet": "9. Diabetes.", "मधुमेह": "9. Diabetes.", "डायबिटीज": "9. Diabetes.",
    "ડાયાબિટીસ": "9. Diabetes.", "મધુમેહ": "9. Diabetes.",
    "cancer": "6. Cancer", "कैंसर": "6. Cancer", "કેન્સર": "6. Cancer",
    "cataract": "7. Cataract.", "blind": "3. Blindness", "deaf": "8. Deafness.",
    "appendic": "1. Appendicitis.", "arterioscler": "2. Arteriosclerosis.",
    "dropsy": "16. Dropsy.",
}


def dmr_overlay(question: str, extra: str = "") -> list[Quote]:
    words = re.findall(r"[\w\u0900-\u0aff]+", f"{question} {extra}".lower())
    entries = list(dict.fromkeys(v for stem, v in DMR_DISEASES.items()
                                 if any(w.startswith(stem) for w in words)))
    if not entries:
        return []
    chunks = ledger.load_chunks()
    out = []
    for cid, text in [DMR_SECTION] + [(DMR_SCHEDULE, e) for e in entries]:
        c = chunks.get(cid)
        if c and text in c["text"]:
            out.append(Quote(text, cid, c["doc_title"], c["section"], c["source_url"],
                             c["retrieved_on"], "overlay"))
    return out if len(out) > 1 else []  # the prohibition and its Schedule entry, or nothing


def _passes(hit) -> bool:
    if hit.coverage >= MIN_COVERAGE:
        return True
    return MIN_COSINE is not None and hit.cosine is not None and hit.cosine >= MIN_COSINE


def answer(
    question: str,
    jurisdiction: str = "IN",
    as_of: dt.date | str | None = None,
    index: Index | None = None,
    k: int = 3,
) -> Answer:
    day = dt.date.fromisoformat(as_of) if isinstance(as_of, str) else (as_of or dt.date.today())
    code = normalize_jurisdiction(jurisdiction)
    idx = index or default_index()
    tr = translate(question)
    # hi/gu: coverage and best_span run on the glossary terms (unknown words kept, so they
    # still count against coverage); dense retrieval sees the original + the translation.
    terms = tr.terms if tr else list(dict.fromkeys(tokenize(question)))
    query = f"{question} {tr.english}" if tr else question
    out = Answer(terms, code, day.isoformat(), idx.corpus_version, abstain=True)
    if tr:
        out.translation = {"lang": tr.lang, "english": tr.english, "unknown": tr.unknown,
                           "machine": tr.machine}

    entry = _find_instrument(question, tr.english if tr else "")
    superseded: set[str] = set()
    if entry is not None and entry.jurisdiction == code:
        res = ledger.resolve_entry(entry, day)
        out.status_line = res.status_line()
        out.status = {
            "instrument": res.instrument,
            "status": res.status,
            "sub_judice": res.sub_judice,
            "summary": res.summary,
            "segment_from": res.segment_from and res.segment_from.isoformat(),
            "segment_to": res.segment_to and res.segment_to.isoformat(),
            "stale": res.stale,
            "last_verified": res.last_verified and res.last_verified.isoformat(),
            "abstain": res.abstain,
            "reason": res.reason,
            # the whole dated timeline, so the UI can show *which* segment this date falls in
            "timeline": [{"from": seg.start.isoformat(), "to": seg.end and seg.end.isoformat(),
                          "status": seg.status, "sub_judice": seg.sub_judice}
                         for seg in entry.timeline],
        }
        chunks = ledger.load_chunks()
        for ev in res.evidence:
            c = chunks[ev.chunk_id]
            out.quotes.append(Quote(ev.quote, ev.chunk_id, c["doc_title"], c["section"],
                                    ev.source_url, c["retrieved_on"], "status_evidence"))
        # Evidence for a segment that does NOT apply on this date must not reappear as a
        # "retrieved passage" — e.g. the 2024 stay quote shown under a 2025 answer.
        current = {e.chunk_id for e in res.evidence}
        superseded = {
            e.chunk_id for seg in entry.timeline for e in seg.evidence
        } - current
        if res.abstain:
            out.reason = res.reason
            return out  # never answer a status question the ledger cannot date

    if entry is not None and entry.jurisdiction == code:
        out.quotes += dmr_overlay(question, tr.english if tr else "")
    out.retrieval = idx.mode
    hits = [h for h in idx.retrieve(query, code, day, k=k, terms=terms) if _passes(h)]
    seen = {q.chunk_id for q in out.quotes}
    for h in hits:
        c = h.chunk
        if c["chunk_id"] in seen or c["chunk_id"] in superseded:
            continue
        out.quotes.append(Quote(best_span(c["text"], terms), c["chunk_id"], c["doc_title"],
                                c["section"], c["source_url"], c["retrieved_on"], "retrieved"))

    if not out.quotes:
        out.reason = (
            f"no source in The Library for jurisdiction {code} as of {day.isoformat()} "
            "covers this question"
        )
        return out
    out.abstain = False
    if out.status and not out.status["stale"]:
        out.confidence = "high"
    elif hits and hits[0].coverage >= 0.85:
        out.confidence = "medium"
    else:
        out.confidence = "low"
    return out
