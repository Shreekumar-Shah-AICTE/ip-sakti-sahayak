"""The Proving Ground — evaluation runner.

Runs every question set in eval/sets/ through IP-SAKTI Sahayak and the vanilla-RAG
baseline, writes eval/results/<set>-<corpus12>.json (corpus hash, commit, date, machine),
and with --gate fails the build when a BENCH_SPEC §4 gate regresses.

Temporal accuracy (set A), same metric for both systems: the FIRST cited chunk must be
evidence for the ledger segment that applies on the as-of date. For our system the
predicted status must also match.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "eval"))

from baselines import vanilla_rag  # noqa: E402

from api import ledger  # noqa: E402
from api.answer import answer  # noqa: E402
from api.retriever import default_index, normalize_jurisdiction  # noqa: E402

SETS = ROOT / "eval" / "sets"
RESULTS = ROOT / "eval" / "results"
GATES = {
    "temporal_margin_pts": 30.0,  # ours - baseline, percentage points
    "citation_exactness": 1.0,
    "abstention_accuracy": 1.0,
    "jurisdiction_leakage": 0,
}


def _norm(s: str) -> str:
    return " ".join(s.split())


def _segment_evidence(as_of: str) -> set[str]:
    entry = ledger.find("Rule 170")
    day = dt.date.fromisoformat(as_of)
    for seg in entry.timeline:
        if seg.covers(day):
            return {e.chunk_id for e in seg.evidence}
    return set()


def _commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "unknown"
    except OSError:
        return "unknown"


def run_set(path: Path) -> dict:
    qs = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    chunks = {c["chunk_id"]: c for c in default_index().chunks}
    rows, lat = [], []
    for q in qs:
        t0 = time.perf_counter()
        a = answer(q["question"], q["jurisdiction"], q["as_of"])
        lat.append((time.perf_counter() - t0) * 1000)
        base = vanilla_rag.retrieve(q["question"], q["jurisdiction"])
        exp = q["expect"]
        code = normalize_jurisdiction(q["jurisdiction"])
        cited = [x.chunk_id for x in a.quotes]
        row = {
            "id": q["id"], "set": q["set"], "lang": q.get("lang", "en"), "abstain": a.abstain,
            "status": a.status and a.status["status"], "cited": cited,
            "baseline_top": base[0]["chunk_id"] if base else None,
            "quotes_exact": all(_norm(x.text) in _norm(chunks[x.chunk_id]["text"])
                                for x in a.quotes),
            "leak": sum(chunks[c]["jurisdiction"] != code for c in cited),
        }
        if q["set"] == "A":
            ev = _segment_evidence(q["as_of"])
            row["ok"] = bool(cited) and cited[0] in ev and a.status["status"] == exp["status"]
            row["baseline_ok"] = bool(base) and base[0]["chunk_id"] in ev
        elif q["set"] == "D":
            row["ok"] = a.abstain
        elif q["set"] == "L":
            row["ok"] = not a.abstain and any(c.startswith(exp["doc"] + "#") for c in cited)
            row["baseline_ok"] = any(c["chunk_id"].startswith(exp["doc"] + "#") for c in base)
        else:  # B
            row["ok"] = row["leak"] == 0
        rows.append(row)

    def frac(rs, key="ok"):
        return round(sum(bool(r[key]) for r in rs) / len(rs), 4) if rs else None

    by = {s: [r for r in rows if r["set"] == s] for s in "ALBD"}
    answered = [r for r in rows if not r["abstain"]]
    lat.sort()
    metrics = {
        "n": len(rows),
        "temporal_accuracy": frac(by["A"]),
        "temporal_accuracy_baseline": frac(by["A"], "baseline_ok"),
        "library_answer_rate": frac(by["L"]),
        "library_answer_rate_baseline": frac(by["L"], "baseline_ok"),
        "citation_exactness": frac(answered, "quotes_exact"),
        "abstention_accuracy": frac(by["D"]),
        "false_abstentions_on_answerable": sum(r["abstain"] for r in by["A"] + by["L"]),
        "jurisdiction_leakage": sum(r["leak"] for r in rows),
        # Per-language LAR (multilingual set): the Glossary's effect must be visible per language.
        "library_answer_rate_by_lang": {
            lg: frac([r for r in by["L"] if r["lang"] == lg])
            for lg in sorted({r["lang"] for r in by["L"]})
        } if len({r["lang"] for r in rows}) > 1 else None,
        "latency_ms_p50": round(statistics.median(lat), 2) if lat else None,
        "latency_ms_p95": round(lat[int(0.95 * (len(lat) - 1))], 2) if lat else None,
    }
    return {
        "set": path.stem,
        "corpus_version": default_index().corpus_version,
        "commit": _commit(),
        "date": dt.date.today().isoformat(),
        "machine": f"{platform.system()} {platform.machine()} py{platform.python_version()}",
        "mode": "keyless",
        "retrieval": default_index().mode,
        "dense": default_index().dense.reason,
        "metrics": metrics,
        "failures": [r for r in rows if not r["ok"]],
        "rows": rows,
    }


def check_gates(m: dict) -> list[str]:
    bad = []
    if m["temporal_accuracy"] is not None:
        margin = 100 * (m["temporal_accuracy"] - m["temporal_accuracy_baseline"])
        if margin < GATES["temporal_margin_pts"]:
            bad.append(f"temporal margin {margin:.1f} pts < {GATES['temporal_margin_pts']}")
    if m["citation_exactness"] is not None and m["citation_exactness"] < 1.0:
        bad.append(f"citation exactness {m['citation_exactness']} < 1.0")
    if m["abstention_accuracy"] is not None and m["abstention_accuracy"] < 1.0:
        bad.append(f"abstention accuracy {m['abstention_accuracy']} < 1.0")
    if m["jurisdiction_leakage"] > 0:
        bad.append(f"jurisdiction leakage {m['jurisdiction_leakage']} > 0")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", action="store_true", help="exit non-zero if any gate fails")
    ap.add_argument("--write", action="store_true", help="write eval/results/<set>-<hash>.json")
    args = ap.parse_args()
    failed = []
    default_index().dense.load()  # synchronous here: the eval must know its mode up front
    for path in sorted(SETS.glob("*.yaml")):
        res = run_set(path)
        m = res["metrics"]
        print(f"The Proving Ground [{res['set']}] n={m['n']} corpus={res['corpus_version'][:19]} "
              f"retrieval={res['retrieval']} ({res['dense']})")
        for k, v in m.items():
            if k != "n":
                print(f"  {k}: {v}")
        print(f"  failures: {[r['id'] for r in res['failures']]}")
        if args.write:
            RESULTS.mkdir(exist_ok=True)
            tag = "" if res["retrieval"] == "bm25" else f"-{res['retrieval']}"
            out = RESULTS / f"{res['set']}-{res['corpus_version'].split(':')[-1][:12]}{tag}.json"
            out.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        failed += [f"{res['set']}: {g}" for g in check_gates(m)]
    for f in failed:
        print("GATE FAIL", f)
    return 1 if (args.gate and failed) else 0


if __name__ == "__main__":
    sys.exit(main())
