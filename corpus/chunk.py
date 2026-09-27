"""The Library — chunker and manifest builder.

Splits every extracted text in corpus/text into ~200-token chunks (160 words,
30-word overlap) that never cross a section boundary, carries every provenance
field onto each chunk, and writes:

    corpus/chunks.jsonl   one chunk per line
    corpus/manifest.json  sorted document records + corpus_version

corpus_version = "sha256:" + sha256 of the canonical JSON of the sorted document
records (each record includes the text hash). It changes whenever any document's
bytes, extracted text or metadata changes, and it is stamped on every chunk and
every answer.

Chunk text is the source text with runs of whitespace collapsed to one space.
Nothing else is altered, so a quote that is a substring of a chunk is a verbatim
quote of the source (modulo line-wrapping whitespace).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEXT = HERE / "text"
PROV = HERE / "provenance"
CHUNKS = HERE / "chunks.jsonl"
MANIFEST = HERE / "manifest.json"

WORDS_PER_CHUNK = 160  # ~200 tokens for English legal text
OVERLAP = 30  # ~40 tokens
MIN_WORDS = 8  # drop page-number / header debris
# A numbered "section" shorter than this is a list item (e.g. a Schedule entry
# "9. Diabetes."), not a section: it is merged into the preceding section so
# that it is neither dropped nor stranded without its heading.
MIN_SECTION_WORDS = 40

# A section starts at a line such as "170. Prohibition…", "[158B. Guidelines…",
# "3. What are not inventions", "Article 16a", "CHAPTER II", "PART XVI", "THE SCHEDULE".
SECTION_RE = re.compile(
    r"^\s*(?:\d{1,4}\.\s+)?\[*\s*(?:"
    r"(?P<num>\d{1,3}[A-Z]{0,2})\.\s*[\[\(\"“‘A-Z]"
    r"|(?P<head>(?:CHAPTER|PART|Article|ARTICLE|SCHEDULE|THE\s+(?:FIRST\s+|SECOND\s+)?SCHEDULE)\b[^\n]{0,60})"
    r")"
)


def normalise(s: str) -> str:
    return " ".join(s.split())


def sections(text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, list[str]]] = [("preamble", [])]
    for line in text.replace("\f", "\n").splitlines():
        m = SECTION_RE.match(line)
        if m:
            label = m.group("num") or normalise(m.group("head"))[:40]
            out.append((label, [line]))
        else:
            out[-1][1].append(line)
    merged: list[tuple[str, str]] = []
    for label, lines in out:
        body = "\n".join(lines)
        if merged and len(body.split()) < MIN_SECTION_WORDS:
            merged[-1] = (merged[-1][0], merged[-1][1] + "\n" + body)
        else:
            merged.append((label, body))
    return merged


def chunk_words(words: list[str]) -> list[list[str]]:
    if len(words) <= WORDS_PER_CHUNK:
        return [words]
    step = WORDS_PER_CHUNK - OVERLAP
    return [words[i : i + WORDS_PER_CHUNK] for i in range(0, len(words) - OVERLAP, step)]


def corpus_version(docs: list[dict]) -> str:
    canon = json.dumps(sorted(docs, key=lambda d: d["id"]), sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canon.encode("utf-8")).hexdigest()


def main() -> int:
    docs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(PROV.glob("*.json"))]
    version = corpus_version(docs)
    carry = ("instrument", "jurisdiction", "tier", "effective_from", "effective_to", "fetched_on")
    n = 0
    with CHUNKS.open("w", encoding="utf-8") as fh:
        for d in docs:
            text = (TEXT / f"{d['id']}.txt").read_text(encoding="utf-8")
            seq = 0
            for label, body in sections(text):
                for w in chunk_words(body.split()):
                    if len(w) < MIN_WORDS:
                        continue
                    rec = {
                        "chunk_id": f"{d['id']}#{seq:04d}",
                        "doc_id": d["id"],
                        "doc_title": d["title"],
                        "section": label,
                        "text": " ".join(w),
                        "source_url": d["canonical_url"],
                        "fetched_url": d["fetched_url"],
                        "retrieved_on": d["fetched_on"],
                        "corpus_version": version,
                        **{k: d[k] for k in carry if k != "fetched_on"},
                    }
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    seq += 1
                    n += 1
    manifest = {"corpus_version": version, "documents": len(docs), "chunks": n, "records": docs}
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"The Library: {len(docs)} documents, {n} chunks, {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
