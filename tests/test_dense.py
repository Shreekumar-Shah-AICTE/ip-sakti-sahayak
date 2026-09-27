"""The Retriever, dense half: optional, fused by RRF inside the filtered id set."""

import datetime as dt
import json

import pytest

from api import answer as answer_mod
from api.retriever import CHUNKS_PATH, Index, default_index
from api.retriever.dense import INDEX_DIR, Dense

DAY = dt.date(2026, 9, 1)


def _chunks():
    return default_index().chunks


def test_committed_index_matches_library():
    # A re-chunk without `make index` must fail here, not silently cite the wrong text.
    meta = json.loads((INDEX_DIR / "ids.json").read_text(encoding="utf-8"))
    ids = [json.loads(line)["chunk_id"] for line in CHUNKS_PATH.open() if line.strip()]
    assert meta["ids"] == ids
    assert meta["corpus_version"] == _chunks()[0]["corpus_version"]


def test_missing_index_falls_back_to_bm25(tmp_path):
    idx = Index(_chunks())
    idx._dense = Dense(idx.chunks, index_dir=tmp_path)
    assert idx.dense.load() is False and "no dense index" in idx.dense.reason
    assert idx.mode == "bm25"
    q = "Who can access the Traditional Knowledge Digital Library?"
    assert [h.chunk["chunk_id"] for h in idx.retrieve(q, "IN", DAY)] == [
        h.chunk["chunk_id"] for h in idx.search(q, "IN", DAY)
    ]
    a = answer_mod.answer(q, "IN", DAY, index=idx)
    assert not a.abstain and a.retrieval == "bm25"


def test_stale_index_is_refused(tmp_path):
    (tmp_path / "ids.json").write_text(json.dumps({"ids": [], "corpus_version": "x"}))
    (tmp_path / "embeddings.npy").write_bytes(b"")
    d = Dense(_chunks(), index_dir=tmp_path)
    assert d.load() is False and not d.ready


def test_env_switch_disables_dense(monkeypatch):
    monkeypatch.setenv("SAHAYAK_DENSE", "0")
    d = Dense(_chunks())
    assert d.load() is False and "SAHAYAK_DENSE=0" in d.reason


class _FakeDense:
    """Deterministic stand-in: ranks a chosen chunk first among whatever ids it is given."""

    ready = True
    reason = "fake"

    def __init__(self, favourite: str, chunks):
        self.fav = next(i for i, c in enumerate(chunks) if c["chunk_id"] == favourite)
        self.seen: list[int] = []

    def rank(self, query, ids, n=50):
        self.seen = list(ids)
        order = ([self.fav] if self.fav in ids else []) + [i for i in ids if i != self.fav]
        return [(i, 0.9 if i == self.fav else 0.1) for i in order[:n]]


def test_rrf_fuses_inside_the_filtered_set():
    idx = Index(_chunks())
    us = next(c["chunk_id"] for c in idx.chunks if c["jurisdiction"] == "US")
    fake = _FakeDense(us, idx.chunks)
    idx._dense = fake
    hits = idx.retrieve("Ayurvedic advertisement diabetes", "IN", DAY, k=10)
    # The favourite is a US chunk: an IN query must never see it, whatever dense thinks.
    assert fake.seen == idx.allowed("IN", DAY)
    assert all(h.chunk["jurisdiction"] == "IN" for h in hits)
    assert us not in {h.chunk["chunk_id"] for h in hits}


def test_rrf_promotes_a_dense_favourite_and_keeps_its_cosine():
    idx = Index(_chunks())
    fav = next(c["chunk_id"] for c in idx.chunks if c["doc_id"] == "in-csir-tkdl-about")
    idx._dense = _FakeDense(fav, idx.chunks)
    hits = idx.retrieve("Traditional Knowledge Digital Library access", "IN", DAY, k=5)
    top = {h.chunk["chunk_id"]: h for h in hits}
    assert fav in top and top[fav].cosine == pytest.approx(0.9)
    assert all(0.0 <= h.coverage <= 1.0 for h in hits)


def test_dense_alone_cannot_pass_the_gate_by_default():
    # MIN_COSINE is None until calibrated on multilingual eval items (DECISIONS D-012).
    assert answer_mod.MIN_COSINE is None
    idx = Index(_chunks())
    idx._dense = _FakeDense(idx.chunks[0]["chunk_id"], idx.chunks)
    a = answer_mod.answer("zzqx unrelated gibberish term", "EU", DAY, index=idx)
    assert a.abstain
