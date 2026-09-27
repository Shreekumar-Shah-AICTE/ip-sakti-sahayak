"""The Status Ledger: Rule 170 resolves correctly on each side of every change."""

import copy
import datetime as dt
from pathlib import Path

import pytest
import yaml

from api.ledger import (
    STATUS_DIR,
    LedgerError,
    load_all,
    load_chunks,
    parse_entry,
    resolve,
    resolve_entry,
)

RAW = yaml.safe_load((STATUS_DIR / "rule_170.yaml").read_text(encoding="utf-8"))
CHUNKS = load_chunks()


@pytest.mark.parametrize(
    "as_of, status, sub_judice",
    [
        ("2024-06-30", "in_force", False),
        ("2024-07-02", "omitted", False),
        ("2024-08-28", "in_force_stayed_omission", True),
        ("2025-08-12", "omitted_stay_vacated", False),
    ],
)
def test_rule_170_as_of(as_of, status, sub_judice):
    r = resolve("Rule 170", as_of)
    assert not r.abstain
    assert r.status == status
    assert r.sub_judice is sub_judice
    assert r.evidence and all(e.source_url.startswith("https://") for e in r.evidence)


def test_segment_boundaries_are_exact():
    assert resolve("Rule 170", "2024-07-01").status == "omitted"
    assert resolve("Rule 170", "2024-08-27").status == "in_force_stayed_omission"
    assert resolve("Rule 170", "2025-08-10").status == "in_force_stayed_omission"
    assert resolve("Rule 170", "2025-08-11").status == "omitted_stay_vacated"


def test_before_first_segment_abstains():
    r = resolve("Rule 170", "2018-12-23")
    assert r.abstain and "interpolate" in r.reason


def test_gap_in_timeline_abstains():
    data = copy.deepcopy(RAW)
    data["timeline"][0]["to"] = "2024-05-31"  # opens a June-2024 gap
    entry = parse_entry(data, CHUNKS)
    assert resolve_entry(entry, dt.date(2024, 6, 15)).abstain
    assert not resolve_entry(entry, dt.date(2024, 5, 31)).abstain


def test_unknown_instrument_abstains():
    assert resolve("Rule 999", "2025-01-01").abstain


def test_staleness_flag_after_last_verified():
    entry = load_all()[0]
    after = entry.last_verified.replace(year=entry.last_verified.year + 1)
    r = resolve("Rule 170", after)
    assert r.stale and "stale" in r.status_line()
    assert not resolve("Rule 170", "2025-08-12").stale


def test_loader_rejects_segment_without_evidence():
    data = copy.deepcopy(RAW)
    del data["timeline"][2]["evidence"]
    with pytest.raises(LedgerError, match="no evidence"):
        parse_entry(data, CHUNKS)


def test_loader_rejects_quote_not_in_chunk():
    data = copy.deepcopy(RAW)
    data["timeline"][3]["evidence"][0]["quote"] = "Rule 170 is struck down forever."
    with pytest.raises(LedgerError, match="verbatim"):
        parse_entry(data, CHUNKS)


def test_loader_rejects_unknown_chunk():
    data = copy.deepcopy(RAW)
    data["timeline"][0]["evidence"][0]["chunk_id"] = "nope#0000"
    with pytest.raises(LedgerError, match="not in The Library"):
        parse_entry(data, CHUNKS)


def test_loader_rejects_overlap():
    data = copy.deepcopy(RAW)
    data["timeline"][1]["to"] = "2024-09-01"
    with pytest.raises(LedgerError, match="overlapping"):
        parse_entry(data, CHUNKS)


def test_every_ledger_file_loads():
    files = sorted(Path(STATUS_DIR).glob("*.yaml"))
    assert files and len(load_all()) == len(files)
