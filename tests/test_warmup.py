"""D-017: the retrieval mode must not change mid-session, so /ask waits for the dense
warm-up to settle and answers 503 (never a different mode) if it cannot."""

import threading

from fastapi.testclient import TestClient

from api import main
from api.retriever.dense import Dense

Q = {"question": "Is Rule 170 in force?", "jurisdiction": "IN", "as_of": "2026-09-01"}


def _quotes(body: dict) -> list[str]:
    return [(q["chunk_id"], q["text"]) for q in body.get("quotes", [])]


def test_two_asks_right_after_start_return_identical_quotes():
    with TestClient(main.app) as client:  # runs the startup warm-up
        a = client.post("/ask", json=Q)
        b = client.post("/ask", json=Q)
        assert a.status_code == b.status_code == 200
        assert _quotes(a.json()) and _quotes(a.json()) == _quotes(b.json())
        h = client.get("/health").json()
        assert h["ready"] is True
        assert h["retrieval"]["mode"] in {"bm25", "hybrid"}


def test_ask_returns_503_while_warm_up_is_unsettled(monkeypatch):
    stuck = Dense([])
    gate = threading.Event()
    monkeypatch.setattr(stuck, "load", lambda: gate.wait(5) and False)
    idx = main.default_index()
    monkeypatch.setattr(idx, "_dense", stuck)
    monkeypatch.setattr(main, "WARM_TIMEOUT_S", 0.05)
    r = TestClient(main.app).post("/ask", json=Q)
    assert r.status_code == 503
    assert r.headers["retry-after"] == "2"
    assert r.json()["warming_up"] is True
    assert TestClient(main.app).get("/health").json()["ready"] is False
    gate.set()


def test_warm_up_is_idempotent_and_settles_when_disabled(monkeypatch):
    monkeypatch.setenv("SAHAYAK_DENSE", "0")
    d = Dense([])
    t1, t2 = d.warm_up(), d.warm_up()
    assert t1 is t2
    assert d.wait(5) and d.settled and not d.ready
