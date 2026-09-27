"""The audit trail must be useful to an auditor and useless to a snoop (KERNEL §7.6, S7)."""

import json

import pytest
from fastapi.testclient import TestClient

from api import audit
from api.main import app

SECRET = "Can I advertise Chyawanprash as a cure for diabetes in Kerala, my name is Meera"


@pytest.fixture
def log(tmp_path, monkeypatch):
    p = tmp_path / "audit.jsonl"
    monkeypatch.setenv("SAHAYAK_AUDIT", "on")
    monkeypatch.setenv("SAHAYAK_AUDIT_LOG", str(p))
    return p


def _write(p, rows):
    p.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows) + "\n",
        encoding="utf-8",
    )


def _rows(p):
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_the_raw_question_never_reaches_the_log(log):
    with TestClient(app) as c:
        assert c.post("/ask", json={"question": SECRET, "jurisdiction": "IN",
                                    "as_of": "2024-08-28"}).status_code == 200
    raw = log.read_text(encoding="utf-8")
    # Nothing the user typed, in whole or in part, and no stray field carrying it.
    for word in ["advertise", "Chyawanprash", "diabetes", "Kerala", "Meera"]:
        assert word.lower() not in raw.lower()
    rows = _rows(log)
    assert len(rows) == 1
    assert set(rows[0]) <= set(audit.FIELDS)
    assert rows[0]["question_sha256"] == audit.question_hash(SECRET)
    assert len(rows[0]["question_sha256"]) == 64


def test_the_row_records_the_decision_so_it_can_be_challenged(log):
    with TestClient(app) as c:
        c.post("/ask", json={"question": "Is Rule 170 in force?", "jurisdiction": "IN",
                             "as_of": "2024-08-28"})
    row = _rows(log)[0]
    assert row["jurisdiction"] == "IN"
    assert row["as_of"] == "2024-08-28"
    assert row["status"] == "in_force_stayed_omission"
    assert row["abstain"] is False
    assert row["chunk_ids"] and all(isinstance(c, str) for c in row["chunk_ids"])


def test_the_same_question_hashes_the_same_and_a_different_one_does_not():
    assert audit.question_hash("Is Rule 170 in force?") == audit.question_hash(
        "  is rule 170 IN FORCE? ")
    assert audit.question_hash("Is Rule 170 in force?") != audit.question_hash(
        "Is Rule 171 in force?")


def test_the_chain_detects_an_edited_or_deleted_row(log):
    with TestClient(app) as c:
        for as_of in ["2024-06-30", "2024-07-02", "2025-08-12"]:
            c.post("/ask", json={"question": "Is Rule 170 in force?", "jurisdiction": "IN",
                                 "as_of": as_of})
    intact, n, reason = audit.verify(log)
    assert (intact, n, reason) == (True, 3, "")

    rows = _rows(log)
    rows[1]["as_of"] = "2026-01-01"  # someone rewrites history
    _write(log, rows)
    intact, _, reason = audit.verify(log)
    assert not intact and "row 2" in reason

    kept = _rows(log)
    _write(log, kept[:1] + kept[2:])
    intact, _, reason = audit.verify(log)
    assert not intact


def test_audit_can_be_switched_off_entirely(log, monkeypatch):
    monkeypatch.setenv("SAHAYAK_AUDIT", "off")
    with TestClient(app) as c:
        assert c.post("/ask", json={"question": SECRET, "jurisdiction": "IN",
                                    "as_of": "2024-08-28"}).status_code == 200
    assert not log.exists()


def test_an_unwritable_path_does_not_cost_the_user_an_answer(tmp_path, monkeypatch):
    monkeypatch.setenv("SAHAYAK_AUDIT", "on")
    monkeypatch.setenv("SAHAYAK_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    monkeypatch.setattr(audit, "_lock", audit._lock)
    monkeypatch.setattr(audit.Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(OSError("full")))
    with TestClient(app) as c:
        r = c.post("/ask", json={"question": "Is Rule 170 in force?", "jurisdiction": "IN",
                                 "as_of": "2024-08-28"})
    assert r.status_code == 200 and r.json()["status"]["status"]


def test_verify_endpoint_reports_the_verdict_without_leaking_rows(log):
    with TestClient(app) as c:
        c.post("/ask", json={"question": SECRET, "jurisdiction": "IN", "as_of": "2024-08-28"})
        body = c.get("/audit/verify").json()
    assert body == {"enabled": True, "intact": True, "rows": 1, "reason": ""}
