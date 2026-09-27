"""Vanilla-RAG baseline: same corpus, same BM25, NO date filter, NO Status Ledger.

It stands in for a conventional RAG assistant (BENCH_SPEC §3). It still honours the
jurisdiction switch — so the temporal comparison isolates the as-of machinery only.
Its 'answer' is the top-k chunks for the question; it never abstains on status.
"""

from __future__ import annotations

import datetime as dt

from api.retriever import Index, default_index, normalize_jurisdiction, tokenize

FAR_FUTURE = dt.date(9999, 12, 31)


def retrieve(
    question: str,
    jurisdiction: str,
    index: Index | None = None,
    k: int = 3,
) -> list[dict]:
    idx = index or default_index()
    code = normalize_jurisdiction(jurisdiction)
    terms = list(dict.fromkeys(tokenize(question)))
    # No as-of filter: every document of the jurisdiction is eligible, whatever its date.
    ids = [i for i, c in enumerate(idx.chunks) if c["jurisdiction"] == code]
    scored = []
    for i in ids:
        tf, dl = idx.tfs[i], idx.lens[i]
        s = 0.0
        for t in terms:
            f = tf.get(t, 0)
            if f:
                s += idx.idf[t] * f * 2.5 / (f + 1.5 * (0.25 + 0.75 * dl / idx.avgdl))
        if s > 0:
            scored.append((s, idx.chunks[i]))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:k]]
