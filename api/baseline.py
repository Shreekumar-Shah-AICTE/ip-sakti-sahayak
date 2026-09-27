"""The static-RAG baseline, served next to the product for the side-by-side demo.

Same corpus, same BM25, NO as-of filter, NO Status Ledger (BENCH_SPEC §3). It honours the
jurisdiction switch so the comparison isolates the as-of machinery only. It never abstains.
The Proving Ground's vanilla-RAG baseline (eval/baselines/vanilla_rag.py) is this function.
"""

from __future__ import annotations

from api.retriever import Index, default_index, normalize_jurisdiction, tokenize


def retrieve(
    question: str, jurisdiction: str, index: Index | None = None, k: int = 3
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
