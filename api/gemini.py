"""The Gemini adapter — one place that knows which Gemini model names actually answer.

Why a chain, and why measured: Google retires model names for new keys without notice
(`gemini-2.5-flash` returns 404 "no longer available to new users" for keys made in Sep
2026), and the free tier caps each model at ~20 requests a day *per model*. Walking a short
list of names that were probed live (run 16, two fresh keys) turns one exhausted or retired
model into a skipped step instead of a dead feature, and multiplies the free daily budget.

A model that answered 404 or 429 is remembered for the life of the process, so a demo does
not pay a wasted round trip on every question after the quota runs out. A 5xx
(overloaded) moves on to the next model without being remembered. Anything else (a
timeout, a 400) is raised to the caller, whose extractive answer then stands.
Keys are passed in by the caller and never logged, cached or returned.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

# Probed 2026-09-27 with two new free-tier keys (run 16). Lite first on measured latency:
# gemini-3.1-flash-lite answered in 0.9 s; the "thinking" flash models took 12-45 s for the
# same two-sentence prompt, which is a dead demo. Our prompts only ask the model to organise
# quotes it is given, which a lite model does well. The heavier models stay as fallbacks.
# Not listed: gemini-2.5-flash / -lite (404 for new keys) and gemini-3.8-flash (its free
# daily quota was already spent, 429, on first use).
MODELS = (
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-3.5-flash",
    "gemini-3-flash-preview",
)
PRIMARY = MODELS[0]
URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"
TIMEOUT_S = 25

_dead: set[str] = set()  # models that said 404/429 in this process


def chain() -> list[str]:
    """Models to try, in order. SAHAYAK_GEMINI_MODEL pins one to the front."""
    pinned = os.environ.get("SAHAYAK_GEMINI_MODEL", "").strip()
    names = [pinned, *MODELS] if pinned else list(MODELS)
    return [m for m in dict.fromkeys(names) if m not in _dead]


def generate(key: str, system: str, prompt: str, temperature: float = 0.0) -> tuple[str, str]:
    """(text, model_that_answered). Raises RuntimeError when every model is unavailable."""
    body = json.dumps({
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature},
    }).encode()
    last: Exception | None = None
    for model in chain():
        req = urllib.request.Request(URL.format(model), body, method="POST", headers={
            "Content-Type": "application/json", "User-Agent": "ip-sakti-sahayak/0.1",
            "x-goog-api-key": key})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:  # noqa: S310 fixed URL
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (404, 429):  # retired for this key, or today's quota is spent
                _dead.add(model)
                continue
            if e.code in (500, 502, 503, 504):  # overloaded right now: try the next model
                last = e
                continue
            raise
        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
        if text.strip():
            return text, model
    if last is not None:
        raise last
    raise RuntimeError("no Gemini model available for this key right now (quota or retired)")
