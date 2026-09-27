"""The Retriever v0: BM25 over The Library, filtered *before* ranking.

Why filter first: if we ranked everything and filtered afterwards, a strong match from
the wrong jurisdiction or a document not yet in existence on the as-of date could push
the right chunk out of the top-k. Computing the allowed id-set first makes the switches
hard constraints, not hints. Pure Python, no keys, no network: the keyless path.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CHUNKS_PATH = ROOT / "corpus" / "chunks.jsonl"

# UI labels -> corpus jurisdiction codes.
JURISDICTIONS = {"IN": "IN", "US": "US", "EU": "EU", "WIPO": "WIPO", "WIPO-track": "WIPO"}

STOPWORDS = set(
    """a an and are as at be by can do does for from has have how i if in into is it its
    me my of on or our s shall should so that the their them then there these this to
    under was we what when where which who whom why will with would you your about any
    all also am been being but did get got had he her him his not no nor only other out
    over she than too up very may must per""".split()
)
K1, B = 1.5, 0.75
RRF_K = 60  # reciprocal-rank-fusion constant (Cormack et al. 2009); not tuned


# The lay→statutory term map (D-013). Users ask "is X patentable?"; the Patents Act says
# "invention" and "patent". Each lay token is also scored as its statutory terms, and counts as
# *covered* in a chunk if the chunk has the token or any mapped term — synonymy, not a free
# pass. Curated by hand, deliberately tiny; every entry needs an eval item that motivated it
# (DECISIONS D-013). Never add an entry just to make a must-abstain item answer.
TERM_MAP: dict[str, tuple[str, ...]] = {
    "patentable": ("patent", "invention"),
    "patentability": ("patent", "invention"),
}


def expand(terms: list[str]) -> list[str]:
    """Query terms plus their mapped statutory terms, de-duplicated, original order first."""
    out = list(terms)
    for t in terms:
        out.extend(x for x in TERM_MAP.get(t, ()) if x not in out)
    return out


def tokenize(text: str) -> list[str]:
    toks = re.findall(r"[a-z0-9]+", text.lower())
    out = []
    for t in toks:
        if t in STOPWORDS or len(t) < 2:
            continue
        if len(t) > 4 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        out.append(t)
    return out


def normalize_jurisdiction(value: str) -> str:
    try:
        return JURISDICTIONS[value]
    except KeyError as exc:
        raise ValueError(f"unknown jurisdiction {value!r}") from exc


@dataclass(frozen=True)
class Hit:
    chunk: dict
    score: float
    coverage: float  # share of distinct query terms present in the chunk
    cosine: float | None = None  # dense similarity, when the dense half contributed


class Index:
    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        self.tfs = [Counter(tokenize(c["text"] + " " + c.get("section", ""))) for c in chunks]
        self.lens = [sum(tf.values()) for tf in self.tfs]
        self.avgdl = sum(self.lens) / max(len(self.lens), 1)
        df: Counter = Counter()
        for tf in self.tfs:
            df.update(tf.keys())
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}
        self.corpus_version = chunks[0]["corpus_version"] if chunks else ""
        self._dense = None  # created on first use of .dense; stays None in pure-BM25 runs

    def allowed(self, jurisdiction: str, as_of: dt.date) -> list[int]:
        """Chunk ids that pass the Two Switches. Unstated dates are not excluded."""
        code = normalize_jurisdiction(jurisdiction)
        ids = []
        for i, c in enumerate(self.chunks):
            if c["jurisdiction"] != code:
                continue
            start, end = c.get("effective_from"), c.get("effective_to")
            if start and dt.date.fromisoformat(start) > as_of:
                continue
            if end and dt.date.fromisoformat(end) < as_of:
                continue
            ids.append(i)
        return ids

    def _bm25(self, terms: list[str], ids: list[int], base: list[str] | None = None) -> list[Hit]:
        """BM25 over `terms`; coverage is measured on `base` (the user's terms) when given."""
        hits = []
        for i in ids:
            tf, dl = self.tfs[i], self.lens[i]
            score = 0.0
            for t in terms:
                f = tf.get(t, 0)
                if not f:
                    continue
                score += self.idf[t] * f * (K1 + 1) / (f + K1 * (1 - B + B * dl / self.avgdl))
            if score > 0:
                hits.append(Hit(self.chunks[i], score, self._coverage(base or terms, i)))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits

    def _coverage(self, terms: list[str], i: int) -> float:
        """Share of the user's own terms present in chunk i (a mapped synonym counts)."""
        tf = self.tfs[i]
        got = sum(1 for t in terms if tf.get(t) or any(tf.get(x) for x in TERM_MAP.get(t, ())))
        return got / len(terms) if terms else 0.0

    def search(self, query: str, jurisdiction: str, as_of: dt.date, k: int = 5,
               terms: list[str] | None = None) -> list[Hit]:
        """BM25 only (the keyless path, and what the vanilla baseline mirrors).

        `terms` overrides tokenisation of `query` (The Glossary passes translated hi/gu terms).
        """
        terms = terms if terms is not None else list(dict.fromkeys(tokenize(query)))
        if not terms:
            return []
        ids = self.allowed(jurisdiction, as_of)  # filter BEFORE rank
        return self._bm25(expand(terms), ids, terms)[:k]

    @property
    def dense(self):
        if self._dense is None:
            from api.retriever.dense import Dense

            self._dense = Dense(self.chunks)
        return self._dense

    @property
    def mode(self) -> str:
        return "hybrid" if self._dense is not None and self._dense.ready else "bm25"

    def retrieve(self, query: str, jurisdiction: str, as_of: dt.date, k: int = 5,
                 terms: list[str] | None = None) -> list[Hit]:
        """Hybrid BM25 + dense fused by RRF when the dense index is ready, else BM25.

        Both rankers see the same filtered id set, so fusion cannot reintroduce a chunk the
        Two Switches excluded. Each fused hit keeps its lexical coverage and its cosine, so
        The Answer Contract can gate on evidence rather than on an opaque fused score.
        """
        if self.mode != "hybrid":
            return self.search(query, jurisdiction, as_of, k, terms)
        ids = self.allowed(jurisdiction, as_of)  # filter BEFORE rank
        terms = terms if terms is not None else list(dict.fromkeys(tokenize(query)))
        lexical = self._bm25(expand(terms), ids, terms) if terms else []
        dense = self._dense.rank(query, ids)
        fused: dict[int, float] = {}
        pos = {id(c): i for i, c in enumerate(self.chunks)}
        for r, h in enumerate(lexical):
            j = pos[id(h.chunk)]
            fused[j] = fused.get(j, 0.0) + 1.0 / (RRF_K + r + 1)
        cos = {}
        for r, (j, s) in enumerate(dense):
            cos[j] = s
            fused[j] = fused.get(j, 0.0) + 1.0 / (RRF_K + r + 1)
        order = sorted(fused, key=lambda j: fused[j], reverse=True)[:k]
        return [Hit(self.chunks[j], fused[j], self._coverage(terms, j), cos.get(j)) for j in order]


@lru_cache(maxsize=1)
def default_index(path: Path = CHUNKS_PATH) -> Index:
    with path.open(encoding="utf-8") as fh:
        return Index([json.loads(line) for line in fh if line.strip()])
