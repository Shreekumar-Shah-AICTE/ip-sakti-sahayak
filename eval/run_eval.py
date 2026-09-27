"""The Proving Ground — evaluation runner.

M0: harness stub. With no question sets present it reports zero questions and
passes the gate. Gates (from M6): temporal accuracy >= baseline + 30 points,
citation exactness 100%, abstention accuracy 100% on set D.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

QUESTIONS = Path(__file__).resolve().parent / "questions.yaml"


def load_questions() -> list[dict]:
    if not QUESTIONS.exists():
        return []
    return yaml.safe_load(QUESTIONS.read_text(encoding="utf-8")) or []


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", action="store_true", help="exit non-zero if any gate fails")
    args = ap.parse_args()
    qs = load_questions()
    print(f"The Proving Ground: {len(qs)} questions loaded; no gates active yet (M0).")
    return 0 if args.gate else 0


if __name__ == "__main__":
    sys.exit(main())
