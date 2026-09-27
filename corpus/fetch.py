"""The Library — fetcher and text extractor.

Reads corpus/sources.yaml, downloads each document through the fallback chain
(official URL(s) -> Wayback Machine snapshot of the first URL), stores raw bytes,
extracts verbatim text and writes one provenance record per document.

Usage:
    python corpus/fetch.py            # fetch anything missing, then extract
    python corpus/fetch.py --offline  # re-extract from corpus/raw only (no network)

Why a fallback chain: some Indian government endpoints refuse US-egress traffic.
The step that worked is recorded as `fetch_method`, so "where did this come from"
always has an exact answer.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"  # committed raw bytes (small files)
CACHE = HERE / "cache"  # gitignored raw bytes (large files, re-fetched + sha-verified)
TEXT = HERE / "text"
PROV = HERE / "provenance"
SOURCES = HERE / "sources.yaml"
UA = {"User-Agent": "Mozilla/5.0 (IP-SAKTI Sahayak corpus builder)"}
# Raw files at or below this size are committed; larger ones are re-fetched and
# verified against the recorded sha256 (keeps the public repo clone small).
COMMIT_RAW_MAX_BYTES = 3_000_000


def load_sources() -> list[dict]:
    return yaml.safe_load(SOURCES.read_text(encoding="utf-8"))


def _get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (fixed URL list)
        return r.read()


def _wayback(url: str) -> str | None:
    q = "http://archive.org/wayback/available?url=" + urllib.parse.quote(url, safe="")
    try:
        snap = json.loads(_get(q, 30)).get("archived_snapshots", {}).get("closest")
    except Exception:  # noqa: BLE001 — any failure means "no snapshot"
        return None
    if not snap or not snap.get("available"):
        return None
    # The id_ suffix returns the archived bytes without the Wayback toolbar.
    return re.sub(r"/web/(\d+)/", r"/web/\1id_/", snap["url"])


def _looks_right(kind: str, data: bytes) -> bool:
    if kind == "pdf":
        return data[:5] == b"%PDF-"
    return b"<html" in data[:4096].lower() or b"<!doctype" in data[:4096].lower()


def fetch(src: dict) -> tuple[bytes, str, str]:
    """Return (bytes, fetched_url, fetch_method)."""
    chain = [(u, "official" if i == 0 else f"mirror-{i}") for i, u in enumerate(src["urls"])]
    errors = []
    for url, method in chain:
        try:
            data = _get(url)
            if _looks_right(src["kind"], data):
                return data, url, method
            errors.append(f"{url}: unexpected content")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{url}: {type(e).__name__}")
    wb = _wayback(src["urls"][0])
    if wb:
        data = _get(wb)
        if _looks_right(src["kind"], data):
            return data, wb, "wayback"
    raise RuntimeError(f"{src['id']}: all fetch steps failed: {errors}")


class _Text(HTMLParser):
    BLOCK = {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "td", "th", "table"}
    SKIP = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__()
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def html_text(data: bytes) -> str:
    p = _Text()
    p.feed(data.decode("utf-8", errors="replace"))
    lines = (" ".join(ln.split()) for ln in "".join(p.out).splitlines())
    return "\n".join(ln for ln in lines if ln)


def pdf_text(path: Path, pages: list[str] | None) -> str:
    spans = pages or [None]
    parts = []
    for span in spans:
        cmd = ["pdftotext", "-layout", "-enc", "UTF-8"]
        if span:
            a, _, b = span.partition("-")
            cmd += ["-f", a, "-l", b or a]
        cmd += [str(path), "-"]
        parts.append(subprocess.run(cmd, capture_output=True, check=True).stdout.decode("utf-8"))
    return "\f".join(parts)


def trim(text: str, keep: list[str] | None) -> str:
    if not keep:
        return text
    start, end = keep
    i = text.find(start)
    j = text.find(end, i + 1) if i >= 0 else -1
    if i < 0 or j < 0:
        raise RuntimeError(f"keep_between markers not found: {keep}")
    return text[i : j + len(end)]


def raw_path(src: dict, size: int | None = None) -> Path:
    name = f"{src['id']}.{src['kind']}"
    if size is None:  # lookup: whichever location holds it
        return RAW / name if (RAW / name).exists() else CACHE / name
    return RAW / name if size <= COMMIT_RAW_MAX_BYTES else CACHE / name


def build(src: dict, offline: bool, today: str) -> dict:
    rp = raw_path(src)
    prov_file = PROV / f"{src['id']}.json"
    old = json.loads(prov_file.read_text()) if prov_file.exists() else {}
    if rp.exists():
        data = rp.read_bytes()
        fetched_url = old.get("fetched_url", src["urls"][0])
        method = old.get("fetch_method", "official")
        fetched_on = old.get("fetched_on", today)
    elif offline:
        raise RuntimeError(f"{src['id']}: no raw file and --offline given")
    else:
        data, fetched_url, method = fetch(src)
        rp = raw_path(src, len(data))
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_bytes(data)
        fetched_on = today
    sha = hashlib.sha256(data).hexdigest()
    want = raw_path(src, len(data))
    if rp != want:  # move between raw/ and cache/ if the size rule says so
        want.parent.mkdir(parents=True, exist_ok=True)
        rp.replace(want)
        rp = want
    if old.get("sha256") and old["sha256"] != sha:
        # Source changed upstream: new text, new provenance, and the change is visible in git.
        fetched_on = today
    text = pdf_text(rp, src.get("pages")) if src["kind"] == "pdf" else html_text(data)
    text = trim(text, src.get("keep_between"))
    TEXT.mkdir(parents=True, exist_ok=True)
    (TEXT / f"{src['id']}.txt").write_text(text, encoding="utf-8")
    prov = {
        "id": src["id"],
        "title": src["title"],
        "instrument": src["instrument"],
        "publisher": src["publisher"],
        "jurisdiction": src["jurisdiction"],
        "tier": src["tier"],
        "canonical_url": src["urls"][0],
        "fetched_url": fetched_url,
        "fetch_method": method,
        "fetched_on": fetched_on,
        "sha256": sha,
        "bytes": len(data),
        "raw_committed": len(data) <= COMMIT_RAW_MAX_BYTES,
        "pages": src.get("pages"),
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "effective_from": src.get("effective_from"),
        "effective_to": src.get("effective_to"),
        "version_note": src.get("version_note"),
    }
    PROV.mkdir(parents=True, exist_ok=True)
    prov_file.write_text(json.dumps(prov, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return prov


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--only", help="build a single document id")
    args = ap.parse_args()
    today = dt.date.today().isoformat()
    failed = []
    for src in load_sources():
        if args.only and src["id"] != args.only:
            continue
        try:
            p = build(src, args.offline, today)
            print(f"ok   {p['id']}  {p['fetch_method']}  {p['bytes']}B")
        except Exception as e:  # noqa: BLE001
            failed.append(src["id"])
            print(f"FAIL {src['id']}: {e}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
