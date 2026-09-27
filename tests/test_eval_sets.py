"""The Proving Ground: question sets are well-formed, so a metric cannot silently merge items."""

from pathlib import Path

import yaml

SETS = sorted((Path(__file__).resolve().parent.parent / "eval" / "sets").glob("*.yaml"))


def _items():
    for path in SETS:
        for q in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            yield path.stem, q


def test_ids_unique_across_all_sets():
    ids = [q["id"] for _, q in _items()]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert not dupes, f"duplicate eval ids: {dupes}"


def test_every_item_has_a_checkable_expectation():
    for stem, q in _items():
        assert q["set"] in {"A", "L", "B", "D"}, (stem, q["id"])
        if q["set"] == "L":
            assert q["expect"]["doc"], q["id"]
        if q["set"] == "D":
            assert q["expect"]["abstain"] is True, q["id"]


def test_multilingual_set_covers_hi_and_gu_with_must_abstain_items():
    ml = [q for stem, q in _items() if stem == "multilingual"]
    for lang in ("hi", "gu"):
        mine = [q for q in ml if q.get("lang") == lang]
        assert any(q["set"] == "L" for q in mine), lang
        assert sum(q["set"] == "D" for q in mine) >= 5, lang
