"""The Library: every chunk traces to a URL, a retrieval date and the corpus hash."""

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
sys.path.insert(0, str(CORPUS))
import chunk  # noqa: E402

MANIFEST = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
_LINES = (CORPUS / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
CHUNKS = [json.loads(ln) for ln in _LINES]
PROV_FIELDS = {
    "canonical_url",
    "fetched_url",
    "fetched_on",
    "sha256",
    "publisher",
    "instrument",
    "jurisdiction",
    "effective_from",
    "effective_to",
    "fetch_method",
    "tier",
    "text_sha256",
}


def _iso(s: str) -> bool:
    try:
        dt.date.fromisoformat(s)
        return True
    except (TypeError, ValueError):
        return False


def test_at_least_twelve_tier1_documents():
    tier1 = [d for d in MANIFEST["records"] if d["tier"] == 1]
    assert len(tier1) >= 12, [d["id"] for d in tier1]


def test_corpus_version_recomputes():
    assert chunk.corpus_version(MANIFEST["records"]) == MANIFEST["corpus_version"]
    assert MANIFEST["chunks"] == len(CHUNKS)


@pytest.mark.parametrize("doc", MANIFEST["records"], ids=lambda d: d["id"])
def test_provenance_record_complete(doc):
    assert PROV_FIELDS <= doc.keys()
    assert doc["canonical_url"].startswith(("http://", "https://"))
    method = doc["fetch_method"]
    assert method in {"official", "wayback"} or method.startswith("mirror-")
    assert _iso(doc["fetched_on"])
    text = (CORPUS / "text" / f"{doc['id']}.txt").read_text(encoding="utf-8")
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == doc["text_sha256"]
    committed = list((CORPUS / "raw").glob(f"{doc['id']}.*"))
    if doc["raw_committed"]:
        assert committed, f"{doc['id']}: raw bytes should be committed"
        assert hashlib.sha256(committed[0].read_bytes()).hexdigest() == doc["sha256"]


def test_every_chunk_traces_to_url_date_and_corpus_hash():
    ids = {d["id"] for d in MANIFEST["records"]}
    seen = set()
    for c in CHUNKS:
        assert c["chunk_id"] not in seen
        seen.add(c["chunk_id"])
        assert c["doc_id"] in ids
        assert c["source_url"].startswith(("http://", "https://")), c["chunk_id"]
        assert _iso(c["retrieved_on"]), c["chunk_id"]
        assert c["corpus_version"] == MANIFEST["corpus_version"], c["chunk_id"]
        assert c["jurisdiction"] in {"IN", "US", "EU", "WIPO"}
        assert c["text"].strip()


def _has(doc_id: str, phrase: str) -> bool:
    return any(phrase in c["text"] for c in CHUNKS if c["doc_id"] == doc_id)


# Verbatim anchors for the demo instruments. If a re-fetch changes these, the
# Status Ledger evidence must be re-checked by a human before shipping.
DR22, DR24 = "in-drugs-rules-1945-compiled-2022", "in-drugs-rules-1945-compiled-2024-09"
SC = "in-sc-wpc-645-2022-order-2025-08-11"
ANCHORS = [
    (DR22, "Prohibition of advertisements of Ayurvedic, Siddha or Unani"),
    (DR24, "Omitted by G.S.R 360(E) dated 01.07.2024 (w.e.f. 01.07.2024)."),
    (
        DR24,
        "Ins. by G.S.R. 1230(E), dated 21st December, 2018 (w.e.f. 24-12-2018).",
    ),
    (SC, "Rule 170 shall remain on the statute book and in force."),
    (SC, "interim order dated 27.08.2024 stands vacated."),
    ("in-dmr-act-1954", "9. Diabetes."),
    ("in-bd-abs-regulations-2025", "Above 5 crore to 50 crore 0.2%"),
    ("in-csir-tkdl-about", "access of TKDL is available to sixteen Patent Offices"),
    ("in-bd-amendment-act-2023", "“codified traditional knowledge” means the knowledge"),
    (
        "in-fssai-ayurveda-aahara-regulations-2022",
        "“Ayurveda Aahara” means a food prepared in accordance with the recipes or ingredients",
    ),
]


@pytest.mark.parametrize("doc_id,phrase", ANCHORS)
def test_demo_anchor_is_verbatim_in_a_chunk(doc_id, phrase):
    assert _has(doc_id, phrase), f"{doc_id}: {phrase!r} not found verbatim in any chunk"


def test_no_tkdl_database_content():
    # TKDL is a pointer only (KERNEL 7.8): the only TKDL document is CSIR's public "about" page.
    tk = [d["id"] for d in MANIFEST["records"] if "tkdl" in d["id"]]
    assert tk == ["in-csir-tkdl-about"]


def test_truncated_pdf_is_rejected():
    import fetch  # noqa: E402 — corpus/ is on sys.path above

    assert fetch._looks_right("pdf", b"%PDF-1.6 body %%EOF\n")
    assert not fetch._looks_right("pdf", b"%PDF-1.6 body cut off at 1 MiB")
