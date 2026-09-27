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
from api.retriever import Index, default_index, normalize_jurisdiction, tokenize

MIN_COVERAGE = 0.6  # share of query terms the best chunk must contain
DISCLAIMER = "Guidance with sources, not legal advice. Confirm with a qualified professional."


@dataclass
class Quote:
    text: str
    chunk_id: str
    doc_title: str
    section: str
    source_url: str
    retrieved_on: str
    role: str  # "status_evidence" | "retrieved"


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


def _find_instrument(question: str) -> ledger.Entry | None:
    q = question.lower()
    for entry in ledger.load_all():
        for name in (entry.instrument, *entry.aliases):
            if re.search(r"(?<![a-z0-9])" + re.escape(name.lower()) + r"(?![a-z0-9])", q):
                return entry
    return None


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
    terms = list(dict.fromkeys(tokenize(question)))
    out = Answer(terms, code, day.isoformat(), idx.corpus_version, abstain=True)

    entry = _find_instrument(question)
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

    hits = [h for h in idx.search(question, code, day, k=k) if h.coverage >= MIN_COVERAGE]
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
