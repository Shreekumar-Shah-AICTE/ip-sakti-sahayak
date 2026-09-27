# The Library

Primary legal instruments, full text (not summaries), each with a provenance record.

| Path | What it is |
|---|---|
| `sources.yaml` | The source register: one entry per document, with its fetch chain and version note |
| `fetch.py` | Downloads via the fallback chain (official URL → mirror → Wayback snapshot), extracts verbatim text, writes provenance |
| `chunk.py` | ~200-token chunks that never cross a section boundary; writes `chunks.jsonl` and `manifest.json` |
| `raw/` | Raw source bytes (files ≤ 3 MB). Larger files go to `cache/` (not committed) and are re-fetched and SHA-256 verified |
| `text/` | Extracted text, verbatim (`pdftotext -layout`) |
| `provenance/` | Per document: canonical URL, fetched URL, fetch method, retrieval date, SHA-256 of bytes and text, publisher, instrument, jurisdiction, effective dates |
| `manifest.json` | All provenance records plus `corpus_version` — the SHA-256 of the sorted records, stamped on every chunk and every answer |

Rebuild: `make corpus` (network) or `make corpus-offline` (from `raw/` + `cache/`).

Where a document is a government compilation or reproduction rather than the Gazette
itself, its `version_note` says so. TKDL database content is never included.
