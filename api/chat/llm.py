"""The Conversation — optional general-knowledge LLM (Ayurveda background, casual chat).

Scope: background knowledge only. Legal questions never come here; they go to The Answer
Contract, which quotes The Library or abstains. The system prompt forbids legal statements,
and `scrub()` removes any sentence that still sounds like one (KERNEL 7.3), so the model can
never become a back door for invented law.

Provider: SAHAYAK_CHAT_LLM = auto (default: groq if GROQ_API_KEY, else gemini if
GEMINI_API_KEY) | groq | gemini | none. Replay cache (`api/chat/replay/`, keyed by sha256 of
provider+model+prompt) is read first, so recorded demo answers work offline; set
SAHAYAK_CHAT_RECORD=1 to write new live answers into it. Keys are read from the environment
only and never logged, cached or returned.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from api import config, gemini
from api.synth import _post

REPLAY_DIR = Path(__file__).resolve().parent / "replay"
MODELS = {  # Gemini first, matching api/config.LLM_ORDER: it is the key the README asks for
    "gemini": ("GEMINI_API_KEY", gemini.PRIMARY),
    "groq": ("GROQ_API_KEY", "openai/gpt-oss-120b"),
}

SYSTEM = (
    "You are Sahayak, a warm, concise assistant about Ayurveda inside IP-SAKTI Sahayak, an "
    "Ayurveda IP and regulatory guidance tool built for the Ministry of Ayush / All India "
    "Institute of Ayurveda. Answer general-knowledge and casual questions about Ayurveda "
    "(concepts, doshas, herbs, texts, history, institutions, lifestyle) accurately, in at most "
    "120 words, using **bold** for key terms. Rules: (1) Never state laws, rules, legal "
    "status, licensing, patentability or regulatory requirements, and never give legal advice "
    "— instead say the user can ask that as a legal question and Sahayak will answer from "
    "official sources. (2) Never prescribe treatment or doses and never claim a remedy cures a "
    "disease; for health problems advise seeing a qualified doctor or registered Ayurveda "
    "practitioner. (3) If unsure, say so. (4) Reply in the language of the question "
    "(English, Hindi or Gujarati)."
)

_LEGAL = re.compile(
    r"\b(Act,? \d{4}|Rules?,? \d{4}|Rule \d+|[Ss]ection \d+|[Rr]egulations? \d{4}|is (il)?legal|"
    r"(il)?legally|licen[cs]e (is )?required|patentable|is banned|prohibited by law)\b"
)


def provider() -> str | None:
    """The provider for general Ayurveda chat, or "replay" to answer from the cache only."""
    p = os.environ.get("SAHAYAK_CHAT_LLM", "auto").lower()
    if p == "none":
        return None
    if not config.online():  # offline is a hard floor, whatever keys happen to be around
        return "replay"
    p = config.chat_provider() or "replay"
    return p if p in MODELS and os.environ.get(MODELS[p][0]) else "replay"


def build_prompt(question: str, history: list[dict], background: str | None) -> str:
    lines = [f"{h['role']}: {h['text'][:400]}" for h in history[-6:] if h.get("text")]
    if background:
        lines.append(f"Curated background (reliable): {background}")
    lines.append(f"user: {question}")
    return "\n".join(lines)


def scrub(text: str) -> str:
    """Drop any sentence that makes a legal statement; the Answer Contract owns law."""
    out = []
    for line in text.strip().splitlines():
        parts = re.split(r"(?<=[.!?।])\s+", line)
        kept = " ".join(p for p in parts if not _LEGAL.search(p))
        if kept.strip() or not line.strip():
            out.append(kept.rstrip())
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


def _key(prov: str, model: str, prompt: str) -> str:
    return hashlib.sha256(f"{prov}\n{model}\n{SYSTEM}\n{prompt}".encode()).hexdigest()[:24]


def _live(prov: str, model: str, key: str, prompt: str) -> str:
    if prov == "gemini":  # walks the probed model chain (api/gemini.py)
        return gemini.generate(key, SYSTEM, prompt, temperature=0.3)[0]
    data = _post(
        "https://api.groq.com/openai/v1/chat/completions",
        {"Authorization": f"Bearer {key}"},
        {
            "model": model,
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": prompt},
            ],
        },
    )
    return re.sub(r"<think>.*?</think>", "", data["choices"][0]["message"]["content"], flags=re.S)


def ask(question: str, history: list[dict], background: str | None = None) -> dict | None:
    """{text, provider, model, source} or None when no provider/recording is available."""
    prov = provider()
    if prov is None:
        return None
    candidates = list(MODELS) if prov == "replay" else [prov]
    prompt = build_prompt(question, history, background)
    for p in candidates:  # a recording from any provider is fine offline
        model = MODELS[p][1]
        name = f"{_key(p, model, prompt)}.json"
        path = next((d / name for d in config.cache_dirs("SAHAYAK_CHAT_REPLAY", REPLAY_DIR, "chat")
                     if (d / name).exists()), None)
        if path:
            text = scrub(json.loads(path.read_text(encoding="utf-8"))["text"])
            return (
                {"text": text, "provider": p, "model": model, "source": "replay"} if text else None
            )
    if prov == "replay":
        return None
    key_var, model = MODELS[prov]
    key = os.environ.get(key_var)
    if not key:
        return None
    try:
        raw = _live(prov, model, key, prompt).strip()
    except Exception:  # network, quota, schema: the curated/offline answer stands
        return None
    if raw and config.replay_mode("SAHAYAK_CHAT_REPLAY") == "record":
        # Cache-first online (free-tier quota); SAHAYAK_CHAT_REPLAY=record authors fixtures.
        out = config.cache_write_dir("SAHAYAK_CHAT_REPLAY", REPLAY_DIR, "chat")
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{_key(prov, model, prompt)}.json"
        path.write_text(
            json.dumps(
                {"provider": prov, "model": model, "prompt": prompt, "text": raw},
                ensure_ascii=False,
                indent=1,
            )
            + "\n",
            encoding="utf-8",
        )
    text = scrub(raw)
    return {"text": text, "provider": prov, "model": model, "source": "live"} if text else None
