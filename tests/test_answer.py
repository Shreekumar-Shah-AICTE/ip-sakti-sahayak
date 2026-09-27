"""The Retriever + The Answer Contract: the Two Switches are hard filters."""

import datetime as dt

import pytest
from fastapi.testclient import TestClient

from api.answer import answer
from api.main import app
from api.retriever import default_index

SC = "in-sc-wpc-645-2022-order-2025-08-11"
CHUNKS = {c["chunk_id"]: c for c in default_index().chunks}
client = TestClient(app)


def _verbatim(a):
    for q in a.quotes:
        assert " ".join(q.text.split()) in " ".join(CHUNKS[q.chunk_id]["text"].split())


def test_rule_170_stayed_on_2024_08_28():
    a = answer("Is Rule 170 in force?", "IN", "2024-08-28")
    assert not a.abstain and a.status["status"] == "in_force_stayed_omission"
    assert a.status["sub_judice"] and "sub judice" in a.status_line
    assert any(q.chunk_id.startswith(SC) and q.role == "status_evidence" for q in a.quotes)
    _verbatim(a)


def test_rule_170_vacated_on_2025_08_12():
    a = answer("Is Rule 170 in force?", "IN", "2025-08-12")
    assert a.status["status"] == "omitted_stay_vacated" and a.confidence == "high"
    assert a.quotes[0].chunk_id == f"{SC}#0036"
    _verbatim(a)


def test_status_before_ledger_starts_abstains():
    a = answer("Is Rule 170 in force?", "IN", "2010-01-01")
    assert a.abstain and "interpolate" in a.reason


@pytest.mark.parametrize("jur", ["US", "EU", "WIPO-track"])
def test_jurisdiction_filter_never_leaks_india(jur):
    a = answer("traditional medicine herbal product registration patent", jur, "2026-01-01")
    code = {"WIPO-track": "WIPO"}.get(jur, jur)
    assert all(CHUNKS[q.chunk_id]["jurisdiction"] == code for q in a.quotes)
    assert a.status is None  # Rule 170 is an IN instrument


def test_filter_runs_before_rank():
    idx = default_index()
    early = dt.date(2024, 8, 28)
    assert all(not idx.chunks[i]["chunk_id"].startswith(SC) for i in idx.allowed("IN", early))
    hits = idx.search("interim order stands vacated Rule 170", "IN", early, k=20)
    assert hits and all(not h.chunk["chunk_id"].startswith(SC) for h in hits)


def test_out_of_corpus_question_abstains():
    a = answer("Who won the FIFA World Cup football final?", "IN", "2026-01-01")
    assert a.abstain and not a.quotes and a.reason


def test_codified_tk_is_answered_from_the_library():
    a = answer("What is codified traditional knowledge?", "IN", "2026-01-01")
    assert not a.abstain
    assert any(q.chunk_id.startswith("in-bd-amendment-act-2023") for q in a.quotes)
    _verbatim(a)
    assert "not legal advice" in a.disclaimer


def test_ask_endpoint_contract():
    r = client.post("/ask", json={"question": "Is Rule 170 in force?", "jurisdiction": "IN",
                                  "as_of": "2025-08-12"})
    assert r.status_code == 200
    body = r.json()
    for key in ("abstain", "quotes", "status_line", "confidence", "corpus_version", "as_of"):
        assert key in body
    assert body["quotes"][0]["source_url"].startswith("https://")
    assert "question" not in body  # no user text echoed back or stored


def test_ask_rejects_unknown_jurisdiction():
    r = client.post("/ask", json={"question": "Rule 170", "jurisdiction": "XX"})
    assert r.status_code == 422


@pytest.mark.parametrize(
    "as_of, status",
    [("2024-06-30", "in_force"), ("2024-07-02", "omitted"),
     ("2024-08-28", "in_force_stayed_omission"), ("2025-08-12", "omitted_stay_vacated")],
)
def test_ledger_endpoint(as_of, status):
    body = client.get("/ledger/Rule 170", params={"as_of": as_of}).json()
    assert body["status"] == status and body["evidence"]


def test_superseded_status_evidence_is_not_resurfaced():
    a = answer("Is Rule 170 in force?", "IN", "2025-08-12")
    assert f"{SC}#0019" not in {q.chunk_id for q in a.quotes}  # the 2024 stay quote


# ---- run 12: topic routing to The Status Ledger + the DMR Act overlay (PITCH_DEFENCE §3) ----

DEMO_Q = "Can I advertise this classical formulation as a treatment for diabetes?"


@pytest.mark.parametrize("day,status,evidence", [
    ("2024-06-30", "in_force", "G.S.R. 1230(E)"),
    ("2024-07-02", "omitted", "G.S.R 360(E)"),
    ("2024-08-28", "in_force_stayed_omission", "shall remain on the statute book"),
    ("2025-08-12", "omitted_stay_vacated", "stands vacated"),
])
def test_advertising_question_routes_to_rule_170_without_naming_it(day, status, evidence):
    from api.answer import answer as ans

    a = ans(DEMO_Q, "IN", day).to_dict()
    assert not a["abstain"] and a["status"]["status"] == status
    assert a["quotes"][0]["role"] == "status_evidence"
    assert any(evidence in q["text"] for q in a["quotes"] if q["role"] == "status_evidence")
    overlay = [q for q in a["quotes"] if q["role"] == "overlay"]
    assert [q["text"] for q in overlay][-1] == "9. Diabetes."  # same overlay at every date
    assert all(q["chunk_id"].startswith("in-dmr-act-1954#") for q in overlay)


def test_dmr_overlay_needs_a_schedule_disease_and_verbatim_text():
    from api.answer import dmr_overlay
    from api.ledger import load_chunks

    assert dmr_overlay("Can I advertise a classical formulation for joint pain?") == []
    chunks = load_chunks()
    for q in dmr_overlay("advertise for cancer and diabetes"):
        assert q.text in chunks[q.chunk_id]["text"]


def test_topic_routing_does_not_capture_unrelated_questions():
    from api.answer import _find_instrument

    assert _find_instrument("Can I patent a classical formulation?") is None
    assert _find_instrument("What is the GST rate on Ayurvedic medicines?") is None
    assert _find_instrument("क्या मैं मधुमेह के लिए आयुर्वेदिक दवा का विज्ञापन कर सकता हूँ?")
