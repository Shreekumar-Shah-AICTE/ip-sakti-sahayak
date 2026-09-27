"""The Answer Contract's optional LLM layer (M7): synthesis over already-cited quotes only.

Extractive-first (DECISIONS D-003): the keyless answer is the floor and is never replaced.
When a provider is configured, the model may only *re-organise* the quotes the contract has
already cited; its output is attached as `answer.synthesis` next to them, and is accepted only
if it passes `check()`:

1. every sentence cites at least one quote marker [n] that exists;
2. every number in the text (dates, sections, percentages; compared as integer runs, so
   01.07.2024 == 01-07-2024) appears in a cited quote or the status line;
3. every sentence is *grounded*: at least MIN_GROUNDING of its content words occur in the
   quotes it cites. A sentence with no checkable English words (e.g. a Hindi paraphrase of
   English quotes) is rejected -- it cannot be verified, so it does not ship;
4. no "replace your lawyer" style claims (FTC/DoNotPay; KERNEL 7.4);
5. no sentence contradicts The Status Ledger: when the status line says the instrument is
   omitted, a sentence may not say it is "in force" (and vice versa). Added run 12 after the
   MIN_GROUNDING sweep (DECISIONS D-020) found a fully grounded sentence -- a quoted Amicus
   submission that "the said Rule is still in force" -- replayed at an as-of date on which the
   ledger says the rule is omitted. Lexical grounding cannot see that; polarity can.

Known limit: these are lexical proxies. A sentence can reuse the quotes' words and still
misstate them; that is why synthesis is off by default and always rendered beside the quotes.

A rejected or failed synthesis is reported with its reason and the extractive answer stands.
Abstentions are never synthesised. Quotes and cited chunk ids are never touched.

Record-replay (`api/synth/replay/*.json`, keyed by sha256 of provider+model+prompt) keeps
`make check` offline and deterministic and lets the demo run in airplane mode:
SAHAYAK_LLM_REPLAY=replay (offline default: cache only, no network) | record (online
default: cache, then live, then save to var/cache) | live (no cache). Provider: SAHAYAK_LLM=
auto (default: the first key present, Gemini first; none offline) | gemini | groq |
sarvam | none. Keys come from the environment only and are never logged, cached or returned.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from api import config, gemini
from api.retriever import tokenize

REPLAY_DIR = Path(__file__).resolve().parent / "replay"
TIMEOUT_S = 20
MAX_CHARS = 1500
MIN_GROUNDING = 0.5  # share of a sentence's content words found in its cited quotes
# confirmed by eval/sweep_min_grounding.py (DECISIONS D-020); pinned in tests/test_synth.py

_STATUS = re.compile(r"Status as of [0-9-]+:\s*([a-z_]+)")
_IN_FORCE = re.compile(r"\bin\s+force\b", re.I)
_NEGATED = re.compile(r"\b(not|no longer|never|ceased|isn't|is not)\b[^.;]*\bin\s+force\b"
                      r"|\bno\s+longer\b", re.I)


def ledger_conflict(sentence: str, status_line: str | None) -> bool:
    """True if the sentence asserts the opposite of the ledger's in-force status."""
    m = _STATUS.search(status_line or "")
    if not m or not _IN_FORCE.search(sentence):
        return False
    ledger_in_force = m.group(1).startswith("in_force")
    if not ledger_in_force and not m.group(1).startswith("omitted"):
        return False
    return ledger_in_force == bool(_NEGATED.search(sentence))

# provider -> (key env var, default model)
PROVIDERS = {
    "gemini": ("GEMINI_API_KEY", gemini.PRIMARY),
    "groq": ("GROQ_API_KEY", "openai/gpt-oss-120b"),
    "sarvam": ("SARVAM_API_KEY", "sarvam-105b"),  # sarvam-m deprecated (run 10)
}

SYSTEM = (
    "You organise quoted legal source text for an Ayurveda IP guidance tool. Use ONLY the "
    "numbered quotes given. Do not add any fact, number, date, section or legal proposition "
    "that is not in a quote. End every sentence with the marker(s) of the quote(s) it relies "
    "on, like [1] or [1][2]. At most 5 sentences. Do not give legal advice; do not say the "
    "reader does not need a lawyer. If the quotes do not answer the question, reply exactly: "
    "INSUFFICIENT"
)

BANNED = re.compile(
    r"(instead of a lawyer|no need (for|of) a lawyer|don't need a lawyer|substitute for a "
    r"(lawyer|professional)|guarantee[ds]?|legal advice from us)", re.I)


@dataclass
class Synthesis:
    provider: str
    model: str
    accepted: bool
    text: str | None
    reason: str
    source: str  # "live" | "replay" | "none"

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def build_prompt(question: str, quotes: list[dict], status_line: str | None) -> str:
    lines = [f"Question: {question}"]
    if status_line:
        lines.append(f"Status: {status_line}")
    lines += [f"[{i}] {q['text']} ({q['doc_title']}, {q['section']})"
              for i, q in enumerate(quotes, 1)]
    return "\n".join(lines)


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?।])\s+", text.strip()) if s.strip()]


def check(text: str, quotes: list[dict], status_line: str | None = None,
          min_grounding: float | None = None) -> str | None:
    """None if the synthesis honours the contract, else the reason it is rejected."""
    floor = MIN_GROUNDING if min_grounding is None else min_grounding
    if not text or not text.strip():
        return "empty"
    if text.strip() == "INSUFFICIENT":
        return "model reported the quotes are insufficient"
    if len(text) > MAX_CHARS:
        return f"longer than {MAX_CHARS} characters"
    if BANNED.search(text):
        return "claims to replace professional advice"
    n = len(quotes)
    src = [f"{q['text']} {q.get('doc_title', '')} {q.get('section', '')}" for q in quotes]
    for s in _sentences(text):
        marks = [int(m) for m in re.findall(r"\[(\d+)\]", s)]
        if not marks:
            return f"uncited sentence: {s[:60]!r}"
        if any(m < 1 or m > n for m in marks):
            return f"cites a quote that does not exist: {marks}"
        words = set(tokenize(re.sub(r"\[\d+\]", " ", s))) - {str(m) for m in marks}
        if not words:
            return f"sentence cannot be checked against the quotes: {s[:60]!r}"
        cited = set(tokenize(" ".join(src[m - 1] for m in marks) + " " + (status_line or "")))
        share = len(words & cited) / len(words)
        if share < floor:
            return f"sentence not grounded in its cited quotes ({share:.2f}): {s[:60]!r}"
        if ledger_conflict(s, status_line):
            return f"sentence contradicts The Status Ledger: {s[:60]!r}"
    body = re.sub(r"\[\d+\]", " ", text)
    pool = " ".join(src) + " " + (status_line or "")
    have = {x.lstrip("0") or "0" for x in re.findall(r"\d+", pool)}
    for num in re.findall(r"\d+", body):
        if (num.lstrip("0") or "0") not in have:
            return f"number {num!r} is not in any cited quote"
    return None


def _post(url: str, headers: dict, payload: dict) -> dict:
    req = urllib.request.Request(url, json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json",
                                          "User-Agent": "ip-sakti-sahayak/0.1", **headers})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:  # noqa: S310 (fixed https URLs)
        return json.loads(r.read())


def _call_live(provider: str, model: str, key: str, prompt: str) -> str:
    if provider == "gemini":  # walks the probed model chain (api/gemini.py)
        return gemini.generate(key, SYSTEM, prompt)[0]
    url = {"groq": "https://api.groq.com/openai/v1/chat/completions",
           "sarvam": "https://api.sarvam.ai/v1/chat/completions"}[provider]
    headers = {"Authorization": f"Bearer {key}"}
    if provider == "sarvam":
        headers["api-subscription-key"] = key
    data = _post(url, headers, {"model": model, "temperature": 0, "messages": [
        {"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]})
    text = data["choices"][0]["message"]["content"]
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()  # sarvam-m reasoning


def cache_key(provider: str, model: str, prompt: str) -> str:
    return hashlib.sha256(f"{provider}\n{model}\n{SYSTEM}\n{prompt}".encode()).hexdigest()[:24]


def complete(provider: str, prompt: str, mode: str | None = None) -> tuple[str | None, str, str]:
    """(text, source, error). Replay first; network only in record/live mode with a key."""
    key_var, model = PROVIDERS[provider]
    model = os.environ.get("SAHAYAK_LLM_MODEL", model)
    mode = mode or config.replay_mode("SAHAYAK_LLM_REPLAY")
    name = f"{cache_key(provider, model, prompt)}.json"
    if mode != "live":
        for d in config.cache_dirs("SAHAYAK_LLM_REPLAY", REPLAY_DIR, "synth"):
            if (d / name).exists():
                return json.loads((d / name).read_text(encoding="utf-8"))["text"], "replay", ""
    if mode == "replay":
        return None, "none", "no recorded response (replay mode, network off)"
    key = os.environ.get(key_var)
    if not key:
        return None, "none", f"{key_var} not set"
    try:
        text = _call_live(provider, model, key, prompt)
    except Exception as e:  # network, quota, schema: the extractive answer stands
        code = getattr(e, "code", "")  # an HTTP status is safe to show; a key never is
        return None, "none", f"provider error: {type(e).__name__} {code}".rstrip()
    if mode == "record":
        out = config.cache_write_dir("SAHAYAK_LLM_REPLAY", REPLAY_DIR, "synth")
        out.mkdir(parents=True, exist_ok=True)
        (out / name).write_text(json.dumps({"provider": provider, "model": model, "prompt": prompt,
                                    "text": text}, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")
    return text, "live", ""


def synthesize(answer: dict, question: str, provider: str | None = None) -> dict | None:
    """Attach-able synthesis dict for an answered contract, or None when no provider is set."""
    provider = (provider or config.llm_provider() or "none").lower()
    if provider in ("", "none") or answer.get("abstain"):
        return None
    if provider not in PROVIDERS:
        return Synthesis(provider, "", False, None, "unknown provider", "none").to_dict()
    model = os.environ.get("SAHAYAK_LLM_MODEL", PROVIDERS[provider][1])
    prompt = build_prompt(question, answer["quotes"], answer.get("status_line"))
    text, source, err = complete(provider, prompt)
    if text is None:
        return Synthesis(provider, model, False, None, err, source).to_dict()
    why = check(text, answer["quotes"], answer.get("status_line"))
    return Synthesis(provider, model, why is None, text if why is None else None,
                     why or "passed the contract checks", source).to_dict()
