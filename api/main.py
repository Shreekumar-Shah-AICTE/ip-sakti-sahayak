"""IP-SAKTI Sahayak — FastAPI entry point.

Keyless by design: with no API keys set, the app starts and serves the
extractive core. LLM and translation providers are optional adapters.
"""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from api import ledger
from api.answer import answer, best_span
from api.baseline import retrieve as static_retrieve
from api.passport import abs as abs_calc
from api.passport import categories as passport_cat
from api.retriever import JURISDICTIONS, default_index, tokenize
from api.synth import synthesize

VERSION = "0.0.1"
ROOT = Path(__file__).resolve().parent.parent
WEB_DIST = ROOT / "web" / "dist"

# Optional adapters, detected by environment-variable *name* only.
# Values are never read into responses or logs.
OPTIONAL_ADAPTERS = {
    "llm.gemini": "GEMINI_API_KEY",
    "llm.groq": "GROQ_API_KEY",
    "mt.sarvam": "SARVAM_API_KEY",
    "mt.bhashini": "BHASHINI_API_KEY",
}

app = FastAPI(title="IP-SAKTI Sahayak", version=VERSION)


# D-017: /ask waits for the dense warm-up to *settle* (loaded or failed) so the retrieval
# mode never changes mid-session. Past this bound it answers 503 + Retry-After and the UI
# retries; it never silently answers in a different mode.
WARM_TIMEOUT_S = float(os.environ.get("SAHAYAK_WARM_TIMEOUT", "20"))


@app.on_event("startup")
def _warm_dense() -> None:
    # Background thread: /health and the web shell are up at once while the optional
    # dense encoder loads; /ask holds until the load settles. Keyless either way.
    default_index().dense.warm_up()


def retriever_ready(timeout: float = 0.0) -> bool:
    """True once the retrieval mode is fixed for the life of the process."""
    dense = default_index().dense
    dense.warm_up()  # no-op if startup already began it (e.g. TestClient without lifespan)
    return dense.wait(timeout)


def adapter_status() -> dict[str, bool]:
    """Which optional adapters are configured (True/False only, never the value)."""
    return {name: bool(os.environ.get(var)) for name, var in OPTIONAL_ADAPTERS.items()}


@app.get("/health")
def health() -> dict:
    adapters = adapter_status()
    return {
        "status": "ok",
        "version": VERSION,
        "mode": "keyless" if not any(adapters.values()) else "adapters",
        "adapters": adapters,
        "llm": {"provider": os.environ.get("SAHAYAK_LLM", "none"),
                "replay": os.environ.get("SAHAYAK_LLM_REPLAY", "replay")},
        "ready": retriever_ready(),
        "retrieval": {"mode": default_index().mode, "dense": default_index().dense.reason},
    }


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    jurisdiction: str = "IN"
    as_of: dt.date | None = None


@app.post("/ask")
def ask(req: AskRequest):
    """The Answer Contract. Query text is not logged or stored (KERNEL §7.6)."""
    if req.jurisdiction not in JURISDICTIONS:
        raise HTTPException(422, f"jurisdiction must be one of {sorted(JURISDICTIONS)}")
    if not retriever_ready(WARM_TIMEOUT_S):
        return JSONResponse({"detail": "warming up", "warming_up": True}, status_code=503,
                            headers={"Retry-After": "2"})
    out = answer(req.question, req.jurisdiction, req.as_of).to_dict()
    # Optional LLM layer (M7): organises the cited quotes; never replaces them.
    out["synthesis"] = synthesize(out, req.question)
    return out


class BaselineRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    jurisdiction: str = "IN"


@app.post("/baseline")
def baseline(req: BaselineRequest) -> dict:
    """The static-RAG baseline for the side-by-side demo: no as-of date, no ledger."""
    if req.jurisdiction not in JURISDICTIONS:
        raise HTTPException(422, f"jurisdiction must be one of {sorted(JURISDICTIONS)}")
    terms = list(dict.fromkeys(tokenize(req.question)))
    return {"kind": "static_rag", "uses_as_of": False, "quotes": [
        {"text": best_span(c["text"], terms), "chunk_id": c["chunk_id"],
         "doc_title": c["doc_title"], "section": c["section"], "source_url": c["source_url"]}
        for c in static_retrieve(req.question, req.jurisdiction)]}


@app.get("/ledger/{instrument}")
def ledger_status(instrument: str, as_of: dt.date) -> dict:
    """The Status Ledger: status of an instrument on a date, with evidence."""
    r = ledger.resolve(instrument, as_of)
    return {
        "instrument": r.instrument,
        "as_of": r.as_of.isoformat(),
        "abstain": r.abstain,
        "reason": r.reason,
        "status": r.status,
        "sub_judice": r.sub_judice,
        "summary": r.summary,
        "stale": r.stale,
        "status_line": r.status_line(),
        "evidence": [
            {"chunk_id": e.chunk_id, "quote": e.quote, "ref": e.ref, "source_url": e.source_url}
            for e in r.evidence
        ],
    }


@app.get("/passport/abs")
def passport_abs(
    turnover_inr: int,
    as_of: dt.date | None = None,
    ex_factory_sales_inr: int | None = None,
    high_value: bool = False,
) -> dict:
    """The Passport Compiler: ABS benefit share with the arithmetic shown, as of a date."""
    if turnover_inr < 0 or (ex_factory_sales_inr is not None and ex_factory_sales_inr < 0):
        raise HTTPException(422, "amounts must be non-negative")
    return abs_calc.compute(turnover_inr, as_of, ex_factory_sales_inr, high_value)



@app.get("/passport/{category}")
def passport_category(category: str, as_of: dt.date | None = None) -> dict:
    """The Passport Compiler: a category passport (classical/proprietary/phytopharma), as of."""
    if category not in passport_cat.CATEGORIES:
        known = ", ".join(passport_cat.CATEGORIES)
        raise HTTPException(404, f"unknown category; use one of {known}")
    return passport_cat.compile_passport(category, as_of)

if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
