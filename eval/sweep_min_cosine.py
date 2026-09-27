"""The Proving Ground — MIN_COSINE admission sweep (hybrid mode only).

For each candidate threshold t, a hit is admitted if coverage >= MIN_COVERAGE or cosine >= t
(exactly The Answer Contract's `_passes`). Reports, over every L/D item in eval/sets/:
abstention accuracy (D), library answer rate (L), and the margin between the highest
must-abstain cosine and t. Ledger-handled items (Rule 170 questions) are skipped for D
because the ledger abstains before retrieval. Run: python eval/sweep_min_cosine.py
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api import answer as contract  # noqa: E402
from api.retriever import default_index  # noqa: E402


def collect() -> list[dict]:
    idx = default_index()
    idx.dense.load()
    if idx.mode != "hybrid":
        raise SystemExit(f"dense index not ready ({idx.dense.reason}); sweep needs hybrid mode")
    rows = []
    for path in sorted((ROOT / "eval" / "sets").glob("*.yaml")):
        for q in yaml.safe_load(path.read_text(encoding="utf-8")) or []:
            if q["set"] not in "LD" or contract._find_instrument(q["question"]):
                continue
            day = dt.date.fromisoformat(q["as_of"])
            hits = idx.retrieve(q["question"], q["jurisdiction"], day, k=3)
            rows.append({"id": q["id"], "set": q["set"], "lang": q.get("lang", "en"),
                         "doc": q["expect"].get("doc"), "hits": hits})
    return rows


def score(rows: list[dict], t: float | None) -> dict:
    def ok(h):
        return h.coverage >= contract.MIN_COVERAGE or (
            t is not None and h.cosine is not None and h.cosine >= t)
    out = {}
    for lang in sorted({r["lang"] for r in rows}) + ["all"]:
        rs = [r for r in rows if lang in ("all", r["lang"])]
        d = [r for r in rs if r["set"] == "D"]
        lib = [r for r in rs if r["set"] == "L"]
        abst = sum(not any(ok(h) for h in r["hits"]) for r in d)
        ans = sum(any(ok(h) and h.chunk["chunk_id"].startswith(r["doc"] + "#")
                      for h in r["hits"]) for r in lib)
        out[lang] = (f"{abst}/{len(d)}", f"{ans}/{len(lib)}")
    return out


def main() -> None:
    rows = collect()
    d_max = max((h.cosine or 0) for r in rows if r["set"] == "D" for h in r["hits"])
    print(f"highest must-abstain cosine: {d_max:.3f}")
    for t in (None, 0.45, 0.50, 0.55, 0.56, 0.57, 0.58, 0.60, 0.65):
        print(f"MIN_COSINE={t}: (abstain D, answered L) by lang -> {score(rows, t)}")


if __name__ == "__main__":
    main()
