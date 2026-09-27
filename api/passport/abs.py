"""The Passport Compiler — ABS benefit-share calculator.

Why rules live in YAML: the numbers are law, not code. `rules/abs.yaml` carries every slab
with the chunk_id and verbatim quote it was copied from; this loader refuses to start if a
quote is not in its chunk, so a re-chunk or a typo fails the build instead of shipping a
wrong rate. Money is Decimal (never float) and the arithmetic is returned step by step.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path

import yaml

from api.ledger import _norm, load_chunks

ROOT = Path(__file__).resolve().parent.parent.parent
RULES_PATH = ROOT / "rules" / "abs.yaml"
CRORE = 10_000_000


class RuleError(ValueError):
    """rules/abs.yaml breaks the contract (missing citation, quote not in chunk, bad slabs)."""


@dataclass(frozen=True)
class Citation:
    regulation: str
    chunk_id: str
    quote: str
    source_url: str

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def _cite(raw: dict, chunks: dict[str, dict], where: str) -> Citation:
    cid, quote = raw.get("chunk_id"), raw.get("quote")
    if not cid or not quote:
        raise RuleError(f"{where}: citation needs chunk_id and quote")
    if cid not in chunks:
        raise RuleError(f"{where}: chunk {cid} not in The Library")
    if _norm(quote) not in _norm(chunks[cid]["text"]):
        raise RuleError(f"{where}: quote is not verbatim in {cid}")
    return Citation(str(raw.get("regulation", "")), cid, quote, chunks[cid].get("source_url", ""))


def _cites(items, chunks, where) -> tuple[Citation, ...]:
    if not items:
        raise RuleError(f"{where}: at least one citation required")
    return tuple(_cite(c, chunks, f"{where}[{i}]") for i, c in enumerate(items))


@lru_cache(maxsize=2)
def load_rules(path: Path = RULES_PATH) -> dict:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    chunks = load_chunks()
    slabs = []
    prev_top = 0
    for i, s in enumerate(data["slabs"]):
        where = f"slabs[{i}]"
        if s["above_inr"] != prev_top:
            raise RuleError(f"{where}: slabs must be contiguous from 0")
        slabs.append({
            "id": s["id"], "label": s["label"], "above_inr": s["above_inr"],
            "up_to_inr": s["up_to_inr"], "rate_pct": Decimal(str(s["rate_pct"])),
            "citations": _cites(s.get("citations"), chunks, where),
        })
        prev_top = s["up_to_inr"]
    if prev_top is not None:
        raise RuleError("last slab must be open-ended (up_to_inr: null)")
    hv = data["high_value_uplift"]
    fa = data["form_a"]
    to = data.get("effective_to")
    return {
        "instrument": data["instrument"],
        "jurisdiction": data["jurisdiction"],
        "effective_from": dt.date.fromisoformat(str(data["effective_from"])),
        "effective_to": dt.date.fromisoformat(str(to)) if to else None,
        "commencement": _cites(data.get("commencement"), chunks, "commencement"),
        "base": _cite(data["base"], chunks, "base"),
        "slabs": tuple(slabs),
        "uplift_pct": Decimal(str(hv["pct"])),
        "uplift_citations": _cites(hv.get("citations"), chunks, "high_value_uplift"),
        "upfront_citations": _cites(hv["upfront"].get("citations"), chunks, "upfront"),
        "form_a": {
            "id": fa["id"], "threshold_inr": fa["threshold_inr"], "obligation": fa["obligation"],
            "citations": _cites(fa.get("citations"), chunks, "form_a"),
        },
    }


def _slab_for(turnover: int, slabs) -> dict:
    for s in slabs:
        if turnover > s["above_inr"] or (s["above_inr"] == 0 and turnover >= 0):
            if s["up_to_inr"] is None or turnover <= s["up_to_inr"]:
                return s
    raise AssertionError("unreachable: slabs are contiguous")


def _money(x: Decimal) -> str:
    return str(x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def compute(turnover_inr: int, as_of: dt.date | str | None = None,
            ex_factory_sales_inr: int | None = None, high_value: bool = False) -> dict:
    """ABS benefit share as of a date. Abstains outside the Regulations' validity window."""
    r = load_rules()
    as_of = dt.date.fromisoformat(as_of) if isinstance(as_of, str) else (as_of or dt.date.today())
    head = {"instrument": r["instrument"], "jurisdiction": r["jurisdiction"],
            "as_of": as_of.isoformat(), "effective_from": r["effective_from"].isoformat(),
            "commencement": [c.to_dict() for c in r["commencement"]]}
    if as_of < r["effective_from"] or (r["effective_to"] and as_of > r["effective_to"]):
        return {**head, "abstain": True,
                "reason": (f"The {r['instrument']} came into force on "
                           f"{r['effective_from'].isoformat()}; the as-of date is outside that "
                           "window and the instrument it superseded (the 2014 ABS Guidelines) "
                           "is not in The Library, so no rate is given.")}
    if turnover_inr < 0 or (ex_factory_sales_inr is not None and ex_factory_sales_inr < 0):
        raise ValueError("amounts must be non-negative")
    s = _slab_for(turnover_inr, r["slabs"])
    steps = [f"Annual turnover ₹{turnover_inr:,} falls in slab {s['id']} ({s['label']}) "
             f"→ rate {s['rate_pct']}%."]
    amount = None
    uplift = None
    if ex_factory_sales_inr is None:
        steps.append("No ex-factory sale price given: the rate applies to the annual gross "
                     "ex-factory sale price of the product excluding Government taxes, not to "
                     "turnover, so no amount is computed.")
    else:
        base_amt = Decimal(ex_factory_sales_inr) * s["rate_pct"] / Decimal(100)
        steps.append(f"Base = ex-factory sale price excl. taxes ₹{ex_factory_sales_inr:,} × "
                     f"{s['rate_pct']}% = ₹{_money(base_amt)}.")
        amount = base_amt
        if high_value:
            uplift = base_amt * r["uplift_pct"] / Decimal(100)
            amount = base_amt + uplift
            steps.append(f"High conservation/economic value resource: +{r['uplift_pct']}% "
                         f"= ₹{_money(base_amt)} + ₹{_money(uplift)} = ₹{_money(amount)}.")
    obligations = []
    fa = r["form_a"]
    if turnover_inr > fa["threshold_inr"]:
        obligations.append({"id": fa["id"], "obligation": fa["obligation"],
                            "citations": [c.to_dict() for c in fa["citations"]]})
    notes = []
    if high_value:
        notes.append({"text": "An upfront payment of not less than 5% of the auction/sale/"
                              "purchase price may also be fixed case by case; it is not computed "
                              "here.", "human_judgment_required": True,
                      "citations": [c.to_dict() for c in r["upfront_citations"]]})
    return {
        **head, "abstain": False,
        "turnover_inr": turnover_inr,
        "ex_factory_sales_inr": ex_factory_sales_inr,
        "high_value": high_value,
        "slab": {"id": s["id"], "label": s["label"], "rate_pct": str(s["rate_pct"]),
                 "citations": [c.to_dict() for c in s["citations"]]},
        "base_rule": r["base"].to_dict(),
        "uplift_inr": _money(uplift) if uplift is not None else None,
        "uplift_citations": [c.to_dict() for c in r["uplift_citations"]] if high_value else [],
        "amount_inr": _money(amount) if amount is not None else None,
        "steps": steps,
        "obligations": obligations,
        "notes": notes,
        "disclaimer": "Guidance with sources, not legal advice. The Authority or Board may "
                      "determine benefit sharing case by case.",
    }
