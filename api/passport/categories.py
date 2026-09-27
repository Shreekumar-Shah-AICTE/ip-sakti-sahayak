"""The Passport Compiler — category passports (classical / proprietary / phytopharmaceutical).

Why data, not code: every obligation is a YAML rule carrying a chunk_id and a verbatim quote.
The loader reuses `abs._cite`, so a quote that is not in its chunk fails the build. Passports are
compiled *as of* a date: before `covered_from` (the earliest date The Library can vouch for the
wording) the passport abstains; rules tied to The Status Ledger (e.g. Rule 170) take their status
and evidence from the ledger for that exact date. Judgment calls are risk indicators, not verdicts.
"""

from __future__ import annotations

import datetime as dt
from functools import lru_cache
from pathlib import Path

import yaml

from api.ledger import find, load_chunks, resolve
from api.passport.abs import RuleError, _cite, _cites

ROOT = Path(__file__).resolve().parent.parent.parent
RULES_DIR = ROOT / "rules"
CATEGORIES = ("classical", "proprietary", "phytopharma")
DISCLAIMER = (
    "Guidance with sources, not legal advice. Items marked 'needs human judgment' are "
    "risk indicators; confirm with the licensing authority or a qualified professional."
)


def _day(v, where: str) -> dt.date:
    try:
        return dt.date.fromisoformat(str(v))
    except ValueError as e:
        raise RuleError(f"{where}: bad date {v!r}") from e


def _rule(raw: dict, chunks: dict, where: str) -> dict:
    for k in ("id", "title", "obligation", "confidence"):
        if not raw.get(k):
            raise RuleError(f"{where}: missing {k}")
    if "human_judgment_required" not in raw:
        raise RuleError(f"{where}: human_judgment_required must be explicit")
    if raw["human_judgment_required"] and not (
        raw.get("risk_indicator") and raw.get("guiding_principle")
    ):
        raise RuleError(
            f"{where}: judgment rules need risk_indicator + guiding_principle (S4 rule 6)"
        )
    ledger = raw.get("ledger")
    if ledger:
        if find(ledger) is None:
            raise RuleError(f"{where}: ledger instrument {ledger!r} not in The Status Ledger")
        cites = ()
    else:
        cites = _cites(raw.get("citations"), chunks, where)
    return {
        "id": raw["id"],
        "title": raw["title"],
        "obligation": raw["obligation"],
        "ledger": ledger,
        "citations": cites,
        "confidence": raw["confidence"],
        "human_judgment_required": bool(raw["human_judgment_required"]),
        "risk_indicator": raw.get("risk_indicator"),
        "guiding_principle": raw.get("guiding_principle"),
        "effective_from": _day(raw["effective_from"], where) if raw.get("effective_from") else None,
        "effective_to": _day(raw["effective_to"], where) if raw.get("effective_to") else None,
    }


@lru_cache(maxsize=8)
def load_category(category: str, rules_dir: Path = RULES_DIR) -> dict:
    if category not in CATEGORIES:
        raise KeyError(category)
    chunks = load_chunks()
    data = yaml.safe_load((rules_dir / f"{category}.yaml").read_text(encoding="utf-8"))
    common = yaml.safe_load((rules_dir / "common.yaml").read_text(encoding="utf-8"))
    cls = data["classification"]
    if not (
        cls.get("human_judgment_required")
        and cls.get("risk_indicator")
        and cls.get("guiding_principle")
    ):
        raise RuleError(f"{category}: classification is a judgment call — needs risk indicator")
    rules = [
        _rule(r, chunks, f"{category}.rules[{i}]") for i, r in enumerate(data.get("rules") or [])
    ]
    for i, r in enumerate(common["rules"]):
        if category in r.get("categories", []):
            rules.append(_rule(r, chunks, f"common.rules[{i}]"))
    ids = [r["id"] for r in rules]
    if len(ids) != len(set(ids)):
        raise RuleError(f"{category}: duplicate rule ids")
    return {
        "category": category,
        "title": data["title"],
        "jurisdiction": data["jurisdiction"],
        "covered_from": _day(data["covered_from"], category),
        "definition": _cite(data["definition"], chunks, f"{category}.definition"),
        "classification": cls,
        "rules": tuple(rules),
        "gaps": tuple(data.get("gaps") or ()),
    }


def _ledger_rule(r: dict, as_of: dt.date) -> dict:
    res = resolve(r["ledger"], as_of)
    out = {"status_line": res.status_line(), "abstain": res.abstain}
    if not res.abstain:
        out["status"] = res.status
        out["sub_judice"] = res.sub_judice
        out["summary"] = res.summary
        out["citations"] = [
            {
                "regulation": f"{e.ref} ({e.date.isoformat()})",
                "chunk_id": e.chunk_id,
                "quote": e.quote,
                "source_url": e.source_url,
            }
            for e in res.evidence
        ]
    return out


def compile_passport(category: str, as_of: dt.date | str | None = None) -> dict:
    """Compile one category passport as of a date. Abstains before The Library's coverage."""
    c = load_category(category)
    as_of = dt.date.fromisoformat(as_of) if isinstance(as_of, str) else (as_of or dt.date.today())
    head = {
        "category": category,
        "title": c["title"],
        "jurisdiction": c["jurisdiction"],
        "as_of": as_of.isoformat(),
        "covered_from": c["covered_from"].isoformat(),
        "disclaimer": DISCLAIMER,
    }
    if as_of < c["covered_from"]:
        return {
            **head,
            "abstain": True,
            "reason": (
                f"The Library holds this category's text as compiled to "
                f"{c['covered_from'].isoformat()}; earlier wording is not held, so no "
                "passport is compiled for this date."
            ),
        }
    items, not_in_force = [], []
    for r in c["rules"]:
        if (r["effective_from"] and as_of < r["effective_from"]) or (
            r["effective_to"] and as_of > r["effective_to"]
        ):
            not_in_force.append({"id": r["id"], "title": r["title"]})
            continue
        item = {
            k: r[k]
            for k in (
                "id",
                "title",
                "obligation",
                "confidence",
                "human_judgment_required",
                "risk_indicator",
                "guiding_principle",
            )
        }
        item["citations"] = [x.to_dict() for x in r["citations"]]
        if r["ledger"]:
            item.update(_ledger_rule(r, as_of))
        items.append(item)
    return {
        **head,
        "abstain": False,
        "definition": c["definition"].to_dict(),
        "classification": {
            k: c["classification"][k]
            for k in ("human_judgment_required", "risk_indicator", "guiding_principle")
        },
        "rules": items,
        "not_in_force": not_in_force,
        "gaps": list(c["gaps"]),
    }
