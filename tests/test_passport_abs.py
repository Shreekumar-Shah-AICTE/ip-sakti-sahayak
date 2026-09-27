"""The Passport Compiler — ABS calculator. Slab boundaries come from the gazette table
(reg 4(1)/5(7)): 'Up to 5 crore' is inclusive, 'Above 5 crore to 50 crore' starts strictly above."""

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from api.main import app
from api.passport import abs as abs_calc

CR = 10_000_000
AS_OF = "2026-09-27"
SALES = 100 * CR  # ₹100 crore ex-factory sales → easy mental arithmetic


@pytest.mark.parametrize(
    "turnover, slab, amount",
    [
        (0, "ABS-SLAB-1", "0.00"),
        (5 * CR, "ABS-SLAB-1", "0.00"),
        (5 * CR + 1, "ABS-SLAB-2", "2000000.00"),
        (50 * CR, "ABS-SLAB-2", "2000000.00"),
        (50 * CR + 1, "ABS-SLAB-3", "4000000.00"),
        (250 * CR, "ABS-SLAB-3", "4000000.00"),
        (250 * CR + 1, "ABS-SLAB-4", "6000000.00"),
    ],
)
def test_slab_boundaries(turnover, slab, amount):
    r = abs_calc.compute(turnover, AS_OF, SALES)
    assert not r["abstain"]
    assert r["slab"]["id"] == slab
    assert r["amount_inr"] == amount


def test_high_value_uplift_is_twenty_percent_of_amount_due():
    r = abs_calc.compute(60 * CR, AS_OF, SALES, high_value=True)
    assert r["uplift_inr"] == "800000.00"
    assert r["amount_inr"] == "4800000.00"
    assert r["uplift_citations"] and r["notes"][0]["human_judgment_required"] is True


def test_rate_applies_to_sales_not_turnover():
    r = abs_calc.compute(60 * CR, AS_OF)
    assert r["amount_inr"] is None
    assert "not to turnover" in " ".join(r["steps"])


def test_form_a_threshold_is_strictly_above_one_crore():
    assert abs_calc.compute(1 * CR, AS_OF)["obligations"] == []
    assert abs_calc.compute(1 * CR + 1, AS_OF)["obligations"][0]["id"] == "ABS-FORM-A"


def test_before_commencement_abstains():
    r = abs_calc.compute(60 * CR, "2025-04-29", SALES)
    assert r["abstain"] and "2025-04-30" in r["reason"]
    assert not abs_calc.compute(60 * CR, "2025-04-30", SALES)["abstain"]


def test_every_citation_is_verbatim_in_its_chunk():
    rules = abs_calc.load_rules()
    assert len(rules["slabs"]) == 4
    for s in rules["slabs"]:
        assert all(c.source_url.startswith("https://") for c in s["citations"])


def test_a_forged_quote_fails_the_build(tmp_path: Path):
    data = yaml.safe_load(abs_calc.RULES_PATH.read_text(encoding="utf-8"))
    data["slabs"][1]["citations"][0]["quote"] = "2. Above 5 crore to 50 crore 0.3%"
    bad = tmp_path / "abs.yaml"
    bad.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with pytest.raises(abs_calc.RuleError):
        abs_calc.load_rules.__wrapped__(bad)


def test_endpoint():
    c = TestClient(app)
    r = c.get("/passport/abs", params={"turnover_inr": 60 * CR, "as_of": AS_OF,
                                        "ex_factory_sales_inr": SALES})
    assert r.status_code == 200 and r.json()["amount_inr"] == "4000000.00"
    early = c.get("/passport/abs", params={"turnover_inr": 60 * CR, "as_of": "2024-01-01"})
    assert early.json()["abstain"]
    assert c.get("/passport/abs", params={"turnover_inr": -1}).status_code == 422
