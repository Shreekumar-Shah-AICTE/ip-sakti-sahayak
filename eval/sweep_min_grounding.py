"""The Proving Ground — MIN_GROUNDING sweep over the committed synthesis recordings.

For every recording in api/synth/replay/ (all providers; recordings from BM25 and hybrid
retrieval both live there, keyed by prompt), re-run The Answer Contract's `check()` at each
candidate grounding floor t and report accepted vs withheld. Recordings that fail for a
reason *other* than grounding (uncited sentence, invented number, INSUFFICIENT, ...) are
"contract-violating" regardless of t; the sweep asserts none of them is ever accepted.
It also lists every sentence of every accepted synthesis with its grounding share, lowest
first, so a human can judge support. The sweep does not auto-judge meaning.
Run: python eval/sweep_min_grounding.py [--markdown]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api import synth  # noqa: E402
from api.retriever import tokenize  # noqa: E402

THRESHOLDS = [0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


def parse_prompt(prompt: str) -> tuple[str, list[dict], str | None]:
    """Recover (question, quotes, status_line) from a recorded prompt (see build_prompt)."""
    question, status, quotes = "", None, []
    for line in prompt.split("\n"):
        if line.startswith("Question: "):
            question = line[len("Question: "):]
        elif line.startswith("Status: "):
            status = line[len("Status: "):]
        elif m := re.match(r"\[(\d+)\] (.*)", line):
            # text + "(title, section)" tokenise identically to check()'s own concatenation
            quotes.append({"text": m.group(2), "doc_title": "", "section": ""})
        elif quotes:
            quotes[-1]["text"] += "\n" + line
    return question, quotes, status


def shares(text: str, quotes: list[dict], status: str | None) -> list[tuple[float, str]]:
    out = []
    for s in synth._sentences(text):
        marks = [int(m) for m in re.findall(r"\[(\d+)\]", s)]
        if not marks or any(m < 1 or m > len(quotes) for m in marks):
            continue
        words = set(tokenize(re.sub(r"\[\d+\]", " ", s))) - {str(m) for m in marks}
        if not words:
            continue
        src = " ".join(quotes[m - 1]["text"] for m in marks) + " " + (status or "")
        out.append((len(words & set(tokenize(src))) / len(words), s))
    return out


def load() -> list[dict]:
    rows = []
    for path in sorted(synth.REPLAY_DIR.glob("*.json")):
        rec = json.loads(path.read_text(encoding="utf-8"))
        q, quotes, status = parse_prompt(rec["prompt"])
        base = synth.check(rec["text"], quotes, status, min_grounding=0.0)
        rows.append({"id": path.stem[:8], "provider": rec["provider"], "question": q,
                     "text": rec["text"], "quotes": quotes, "status": status,
                     "violates": base,  # non-grounding contract failure, or None
                     "shares": shares(rec["text"], quotes, status)})
    return rows


def sweep(rows: list[dict]) -> list[dict]:
    table = []
    for t in THRESHOLDS:
        acc = [r for r in rows if synth.check(r["text"], r["quotes"], r["status"], t) is None]
        table.append({"t": t, "accepted": len(acc), "withheld": len(rows) - len(acc),
                      "violating_accepted": sum(1 for r in acc if r["violates"])})
    return table


def main() -> None:
    rows = load()
    table = sweep(rows)
    print(f"{len(rows)} recordings; {sum(1 for r in rows if r['violates'])} violate the "
          "contract for a non-grounding reason")
    print("| t | accepted | withheld | violating accepted |\n|---|---|---|---|")
    for x in table:
        print(f"| {x['t']:.1f} | {x['accepted']} | {x['withheld']} | {x['violating_accepted']} |")
    print("\nSentences of synthesis accepted at the current floor "
          f"({synth.MIN_GROUNDING}), lowest grounding first — judge these by eye:")
    acc = [r for r in rows if synth.check(r["text"], r["quotes"], r["status"]) is None]
    sents = sorted((sh, r["provider"], r["id"], s) for r in acc for sh, s in r["shares"])
    for sh, prov, rid, s in sents:
        print(f"- {sh:.2f} {prov} {rid}: {s[:160]}")
    print("\nWithheld recordings and why:")
    for r in rows:
        why = synth.check(r["text"], r["quotes"], r["status"])
        if why:
            print(f"- {r['provider']} {r['id']} ({r['question'][:50]}): {why[:110]}")


if __name__ == "__main__":
    main()
