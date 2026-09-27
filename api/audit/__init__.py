"""The audit trail — what the system decided, never what the user typed.

KERNEL §7.6 and skill S7: an append-only JSONL record of every /ask. It stores a salted
hash of the question, the switches, the retrieval mode and the chunk ids that were served —
so an auditor can reproduce and challenge a decision — and no query text, ever.

Rows are hash-chained (`prev` → `row_hash`), so deleting or editing a past row is
detectable by `verify()`. Auditability is the point: a regulatory assistant whose past
answers cannot be checked is worth less than one whose can.

Off is a single environment variable, and a failed write never breaks an answer.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import secrets
import threading
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_PATH = ROOT / "var" / "audit.jsonl"

# Fields that may be written. Anything else is dropped rather than trusted: this is the
# list the DPDP note in the README describes, and the test that proves it reads this.
FIELDS = (
    "ts", "question_sha256", "lang_hint", "jurisdiction", "as_of", "mode",
    "chunk_ids", "abstain", "confidence", "instrument", "status",
    "synthesis_provider", "synthesis_accepted", "prev", "row_hash",
)

_lock = threading.Lock()
# No salt configured → a random per-process salt. Hashes then group the questions of one
# session without being linkable to any other run, which is the safer default.
_salt = os.environ.get("SAHAYAK_AUDIT_SALT") or secrets.token_hex(16)


def enabled() -> bool:
    return os.environ.get("SAHAYAK_AUDIT", "on").lower() not in {"off", "0", "false", "no"}


def path() -> Path:
    return Path(os.environ.get("SAHAYAK_AUDIT_LOG") or DEFAULT_PATH)


def question_hash(question: str) -> str:
    """Salted SHA-256 of the normalised question. Not reversible; not a store of the text."""
    return hashlib.sha256((_salt + " " + question.strip().casefold()).encode("utf-8")).hexdigest()


def _row_hash(row: dict[str, Any]) -> str:
    body = json.dumps(
        {k: row[k] for k in row if k != "row_hash"}, sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _last_hash(p: Path) -> str:
    try:
        prev = ""
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    prev = json.loads(line).get("row_hash", "")
        return prev
    except (OSError, json.JSONDecodeError):
        return ""


def record(question: str, answer: dict[str, Any], *, lang_hint: str | None = None) -> dict | None:
    """Append one row for an answered /ask. Returns the row, or None when disabled."""
    if not enabled():
        return None
    status = answer.get("status") or {}
    synth = answer.get("synthesis") or {}
    row: dict[str, Any] = {
        "ts": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "question_sha256": question_hash(question),
        "lang_hint": lang_hint,
        "jurisdiction": answer.get("jurisdiction"),
        "as_of": answer.get("as_of"),
        "mode": answer.get("retrieval_mode") or answer.get("mode"),
        "chunk_ids": [q.get("chunk_id") for q in answer.get("quotes", [])],
        "abstain": bool(answer.get("abstain")),
        "confidence": answer.get("confidence"),
        "instrument": status.get("instrument"),
        "status": status.get("status"),
        "synthesis_provider": synth.get("provider"),
        "synthesis_accepted": synth.get("accepted"),
    }
    p = path()
    try:
        with _lock:
            p.parent.mkdir(parents=True, exist_ok=True)
            row["prev"] = _last_hash(p)
            row["row_hash"] = _row_hash(row)
            assert set(row) <= set(FIELDS), "audit row may only contain declared fields"
            with p.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        # An unwritable audit path must never cost the user their answer.
        return None
    return row


def verify(p: Path | None = None) -> tuple[bool, int, str]:
    """Walk the chain. Returns (intact, rows checked, reason for the first break)."""
    f = p or path()
    if not f.exists():
        return True, 0, ""
    prev = ""
    n = 0
    with f.open("r", encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            n += 1
            if row.get("prev") != prev:
                return False, n, f"row {i}: prev does not match the previous row_hash"
            if row.get("row_hash") != _row_hash(row):
                return False, n, f"row {i}: contents do not match row_hash"
            prev = row["row_hash"]
    return True, n, ""
