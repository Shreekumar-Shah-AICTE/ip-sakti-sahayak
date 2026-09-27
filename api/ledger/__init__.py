"""The Status Ledger: versioned legal-status timelines, resolved as of a date.

Why this exists: the law for Ayurveda IP changed several times in 2024-2025. A status
answer is only correct for a date, so every lookup takes an `as_of` date. Every segment
must cite a chunk in The Library with a verbatim quote; if no segment covers the date,
the ledger abstains instead of guessing (no interpolation).
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
STATUS_DIR = ROOT / "ledger" / "status"
CHUNKS_PATH = ROOT / "corpus" / "chunks.jsonl"

STATUSES = {"in_force", "omitted", "in_force_stayed_omission", "omitted_stay_vacated"}


class LedgerError(ValueError):
    """A ledger file breaks the contract (missing evidence, bad dates, overlap)."""


@dataclass(frozen=True)
class Evidence:
    type: str
    ref: str
    date: dt.date
    chunk_id: str
    quote: str
    source_url: str


@dataclass(frozen=True)
class Segment:
    start: dt.date
    end: dt.date | None
    status: str
    sub_judice: bool
    summary: str
    evidence: tuple[Evidence, ...]

    def covers(self, day: dt.date) -> bool:
        return self.start <= day and (self.end is None or day <= self.end)


@dataclass(frozen=True)
class Entry:
    instrument: str
    instrument_id: str
    jurisdiction: str
    aliases: tuple[str, ...]
    last_verified: dt.date
    steward: str
    timeline: tuple[Segment, ...]


@dataclass(frozen=True)
class Resolution:
    instrument: str
    as_of: dt.date
    abstain: bool
    reason: str = ""
    status: str | None = None
    sub_judice: bool = False
    summary: str = ""
    segment_from: dt.date | None = None
    segment_to: dt.date | None = None
    stale: bool = False
    last_verified: dt.date | None = None
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)

    def status_line(self) -> str:
        """The Answer Contract's 'status as of' line."""
        if self.abstain:
            return f"Status as of {self.as_of.isoformat()}: unknown — {self.reason}"
        line = f"Status as of {self.as_of.isoformat()}: {self.status}"
        if self.sub_judice:
            line += " (sub judice)"
        if self.stale:
            line += f" — ledger last verified {self.last_verified.isoformat()}; may be stale"
        return line


def _date(value, where: str) -> dt.date:
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError as exc:
        raise LedgerError(f"{where}: bad date {value!r}") from exc


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


@lru_cache(maxsize=4)
def load_chunks(path: Path = CHUNKS_PATH) -> dict[str, dict]:
    with path.open(encoding="utf-8") as fh:
        rows = (json.loads(line) for line in fh if line.strip())
        return {r["chunk_id"]: r for r in rows}


def parse_entry(data: dict, chunks: dict[str, dict], where: str = "entry") -> Entry:
    for key in ("instrument", "jurisdiction", "last_verified", "timeline"):
        if not data.get(key):
            raise LedgerError(f"{where}: missing {key}")
    segments: list[Segment] = []
    for i, seg in enumerate(data["timeline"]):
        at = f"{where} segment {i}"
        status = seg.get("status")
        if status not in STATUSES:
            raise LedgerError(f"{at}: unknown status {status!r}")
        evidence_rows = seg.get("evidence") or []
        if isinstance(evidence_rows, dict):
            evidence_rows = [evidence_rows]
        if not evidence_rows:
            raise LedgerError(f"{at}: no evidence — every segment must cite The Library")
        evidence = []
        for ev in evidence_rows:
            cid, quote = ev.get("chunk_id"), ev.get("quote")
            if not cid or not quote:
                raise LedgerError(f"{at}: evidence needs chunk_id and quote")
            chunk = chunks.get(cid)
            if chunk is None:
                raise LedgerError(f"{at}: chunk {cid} not in The Library")
            if _norm(quote) not in _norm(chunk["text"]):
                raise LedgerError(f"{at}: quote not verbatim in {cid}")
            evidence.append(
                Evidence(
                    type=str(ev.get("type", "")),
                    ref=str(ev.get("ref", "")),
                    date=_date(ev.get("date"), at),
                    chunk_id=cid,
                    quote=_norm(quote),
                    source_url=chunk["source_url"],
                )
            )
        start = _date(seg.get("from"), at)
        end = None if seg.get("to") is None else _date(seg["to"], at)
        if end is not None and end < start:
            raise LedgerError(f"{at}: 'to' before 'from'")
        segments.append(
            Segment(start, end, status, bool(seg.get("sub_judice", False)),
                    _norm(str(seg.get("summary", ""))), tuple(evidence))
        )
    segments.sort(key=lambda s: s.start)
    for prev, nxt in zip(segments, segments[1:], strict=False):
        if prev.end is None or prev.end >= nxt.start:
            raise LedgerError(f"{where}: overlapping segments at {nxt.start}")
    return Entry(
        instrument=data["instrument"],
        instrument_id=str(data.get("instrument_id", data["instrument"])),
        jurisdiction=data["jurisdiction"],
        aliases=tuple(data.get("aliases", [])),
        last_verified=_date(data["last_verified"], where),
        steward=str(data.get("steward", "")),
        timeline=tuple(segments),
    )


def load_file(path: Path, chunks: dict[str, dict] | None = None) -> Entry:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return parse_entry(data, chunks if chunks is not None else load_chunks(), path.name)


@lru_cache(maxsize=1)
def load_all(status_dir: Path = STATUS_DIR) -> tuple[Entry, ...]:
    return tuple(load_file(p) for p in sorted(status_dir.glob("*.yaml")))


def find(instrument: str, entries: tuple[Entry, ...] | None = None) -> Entry | None:
    key = instrument.strip().lower()
    for e in entries if entries is not None else load_all():
        names = {e.instrument.lower(), e.instrument_id.lower(), *(a.lower() for a in e.aliases)}
        if key in names:
            return e
    return None


def resolve_entry(entry: Entry, as_of: dt.date) -> Resolution:
    for seg in entry.timeline:
        if seg.covers(as_of):
            return Resolution(
                instrument=entry.instrument,
                as_of=as_of,
                abstain=False,
                status=seg.status,
                sub_judice=seg.sub_judice,
                summary=seg.summary,
                segment_from=seg.start,
                segment_to=seg.end,
                stale=as_of > entry.last_verified,
                last_verified=entry.last_verified,
                evidence=seg.evidence,
            )
    return Resolution(
        instrument=entry.instrument,
        as_of=as_of,
        abstain=True,
        reason="no ledger segment covers this date; the ledger does not interpolate",
        last_verified=entry.last_verified,
    )


def resolve(instrument: str, as_of: dt.date | str) -> Resolution:
    """Status of `instrument` on `as_of`. Abstains if unknown or not covered."""
    day = _date(as_of, "as_of")
    entry = find(instrument)
    if entry is None:
        return Resolution(instrument=instrument, as_of=day, abstain=True,
                          reason="instrument not in The Status Ledger")
    return resolve_entry(entry, day)
