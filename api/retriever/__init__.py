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

    def search(self, query: str, jurisdiction: str, as_of: dt.date, k: int = 5) -> list[Hit]:
        terms = list(dict.fromkeys(tokenize(query)))
        if not terms:
            return []
        hits = []
        for i in self.allowed(jurisdiction, as_of):  # filter BEFORE rank
            tf, dl = self.tfs[i], self.lens[i]
            score, present = 0.0, 0
            for t in terms:
                f = tf.get(t, 0)
                if not f:
                    continue
                present += 1
                score += self.idf[t] * f * (K1 + 1) / (f + K1 * (1 - B + B * dl / self.avgdl))
            if score > 0:
                hits.append(Hit(self.chunks[i], score, present / len(terms)))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]


@lru_cache(maxsize=1)
def default_index(path: Path = CHUNKS_PATH) -> Index:
    with path.open(encoding="utf-8") as fh:
        return Index([json.loads(line) for line in fh if line.strip()])
