"""The Passport Compiler — category passports. Every obligation must cite a verbatim chunk,
judgment calls must be risk indicators, and the passport must be compiled as of the date."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.ledger import _norm, load_chunks
from api.main import app
from api.passport import categories as cat
from api.passport.abs import RuleError

client = TestClient(app)
NOW = "2026-09-27"


@pytest.mark.parametrize("category", cat.CATEGORIES)
def test_every_citation_is_verbatim(category):
    chunks = load_chunks()
    p = cat.compile_passport(category, NOW)
    assert not p["abstain"] and p["rules"]
    cites = [p["definition"]] + [c for r in p["rules"] for c in r["citations"]]
    for c in cites:
        assert _norm(c["quote"]) in _norm(chunks[c["chunk_id"]]["text"]), c
        assert c["source_url"].startswith("http")
    for r in p["rules"]:
        assert r["citations"], f"{r['id']} has no citation"
        if r["human_judgment_required"]:
            assert r["risk_indicator"] and r["guiding_principle"]


def test_classical_passport_rules():
    p = cat.compile_passport("classical", NOW)
    ids = {r["id"] for r in p["rules"]}
    assert {
        "CL-NAMING",
        "CL-LICENCE-EVIDENCE",
        "ADV-RULE-170",
        "ADV-DMR-S3",
        "IP-PATENTS-3P",
    } <= ids
    assert "First Schedule" in p["definition"]["quote"]
    assert p["classification"]["human_judgment_required"] is True


def test_proprietary_passport_rules():
    p = cat.compile_passport("proprietary", NOW)
    ids = {r["id"] for r in p["rules"]}
    assert {"PP-NAMING", "PP-LICENCE-EVIDENCE", "PP-BALYA-SCHEDULE-E1", "ADV-RULE-170"} <= ids
    assert p["definition"]["regulation"].endswith("I(B)(i)")


def test_phytopharma_passport_cites_rule_2ec_and_declares_gap():
    p = cat.compile_passport("phytopharma", NOW)
    assert p["definition"]["regulation"] == "Drugs Rules 1945, Rule 2(ec)"
    assert "minimum four bio-active" in p["definition"]["quote"]
    assert p["gaps"], "licensing pathway is not in The Library — must be declared, not invented"
    assert "ADV-RULE-170" not in {r["id"] for r in p["rules"]}  # Rule 170 is an ASU rule


@pytest.mark.parametrize(
    "as_of, status, sub_judice",
    [
        ("2024-06-30", "in_force", False),
        ("2024-07-02", "omitted", False),
        ("2024-08-28", "in_force_stayed_omission", True),
        ("2025-08-12", "omitted_stay_vacated", False),
    ],
)
def test_rule_170_item_follows_the_ledger_date(as_of, status, sub_judice):
    r = {x["id"]: x for x in cat.compile_passport("classical", as_of)["rules"]}["ADV-RULE-170"]
    assert r["status"] == status and r["sub_judice"] is sub_judice
    assert r["citations"] and as_of in r["status_line"]


def test_abstains_before_library_coverage():
    p = cat.compile_passport("proprietary", "2022-11-16")
    assert p["abstain"] and "2022-11-17" in p["reason"] and "rules" not in p


def test_api_endpoint_and_unknown_category():
    r = client.get("/passport/classical", params={"as_of": NOW})
    assert r.status_code == 200 and r.json()["as_of"] == NOW
    assert client.get("/passport/homeopathy").status_code == 404
    assert (
        client.get("/passport/abs", params={"turnover_inr": 0}).status_code == 200
    )  # route not shadowed


def _write(tmp: Path, rule_yaml: str) -> Path:
    src = cat.RULES_DIR
    (tmp / "common.yaml").write_text(
        (src / "common.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    body = (src / "classical.yaml").read_text(encoding="utf-8")
    head = body.split("rules:\n")[0]
    (tmp / "classical.yaml").write_text(
        head + "rules:\n" + rule_yaml + "gaps: []\n", encoding="utf-8"
    )
    return tmp


def test_loader_rejects_non_verbatim_quote(tmp_path):
    bad = (
        "  - id: X\n    title: t\n    obligation: o\n    confidence: high\n"
        "    human_judgment_required: false\n    citations:\n"
        '      - {regulation: r, chunk_id: "in-drugs-rules-1945-compiled-2022#0034",\n'
        '         quote: "invented law"}\n'
    )
    with pytest.raises(RuleError, match="verbatim"):
        cat.load_category.__wrapped__("classical", _write(tmp_path, bad))


def test_loader_rejects_judgment_rule_without_risk_indicator(tmp_path):
    bad = (
        "  - id: X\n    title: t\n    obligation: o\n    confidence: high\n"
        "    human_judgment_required: true\n    citations:\n"
        '      - {regulation: r, chunk_id: "in-dmr-act-1954#0026", quote: "9. Diabetes."}\n'
    )
    with pytest.raises(RuleError, match="risk_indicator"):
        cat.load_category.__wrapped__("classical", _write(tmp_path, bad))
