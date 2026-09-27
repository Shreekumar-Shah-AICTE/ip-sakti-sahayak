"""The Glossary's fallback: optional machine translation of words the Glossary does not know.

Off by default (`SAHAYAK_MT=none`). With `SAHAYAK_MT=groq|sarvam` only the Glossary's
*unknown* words are sent — never the whole question, never English text. Each word comes back
as English or `?`; a `?`, an empty line, or a non-ASCII reply keeps the word unknown, so it still
counts against coverage. The coverage gate itself is unchanged: MT can supply a term, it can
never lower MIN_COVERAGE. Responses are record-replayed like `api/synth` (same modes via
`SAHAYAK_MT_REPLAY=replay|record|live`, default replay), so the eval is reproducible offline.
Keys come from the environment only and are never logged, cached or returned.
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
PROVIDERS = {
    "gemini": ("GEMINI_API_KEY", gemini.PRIMARY),
    "groq": ("GROQ_API_KEY", "openai/gpt-oss-120b"),
    "sarvam": ("SARVAM_API_KEY", "sarvam-translate:v1"),
}
SYSTEM = (
    "You translate single Hindi or Gujarati words from questions about Indian law, patents and "
    "Ayurveda into English. Reply with exactly one line per input word, in the same order: the "
    "most literal English word or short phrase, lower case, no explanation. If a word is a "
    "function word, a name you cannot translate, or you are unsure, reply with ? on its line."
)


def cache_key(provider: str, model: str, lang: str, words: list[str]) -> str:
    raw = f"{provider}\n{model}\n{SYSTEM}\n{lang}\n" + "\n".join(words)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _call_live(provider: str, model: str, key: str, lang: str, words: list[str]) -> list[str]:
    if provider == "sarvam":
        code = {"hi": "hi-IN", "gu": "gu-IN"}[lang]
        out = []
        for w in words:
            data = _post("https://api.sarvam.ai/translate", {"api-subscription-key": key},
                         {"input": w, "source_language_code": code,
                          "target_language_code": "en-IN", "model": model})
            out.append(str(data.get("translated_text", "?")))
        return out
    if provider == "gemini":  # walks the probed model chain (api/gemini.py)
        return gemini.generate(key, SYSTEM, "\n".join(words))[0].strip().split("\n")
    data = _post("https://api.groq.com/openai/v1/chat/completions",
                 {"Authorization": f"Bearer {key}"},
                 {"model": model, "temperature": 0, "messages": [
                     {"role": "system", "content": SYSTEM},
                     {"role": "user", "content": "\n".join(words)}]})
    text = data["choices"][0]["message"]["content"]
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip().split("\n")


def _clean(reply: str) -> str | None:
    s = reply.strip().lower().strip(" .;:-*\"'")
    s = re.sub(r"^\d+[.)]\s*", "", s)
    if not s or s == "?" or not re.fullmatch(r"[a-z][a-z \-]{0,40}", s):
        return None
    return s


def lookup(lang: str, words: list[str], provider: str | None = None,
           mode: str | None = None) -> dict[str, str]:
    """{word: english} for the words the provider could translate; {} when off or failing."""
    provider = (provider or config.mt_provider() or "none").lower()
    if provider not in PROVIDERS or not words:
        return {}
    key_var, model = PROVIDERS[provider]
    mode = mode or config.replay_mode("SAHAYAK_MT_REPLAY")
    name = f"{cache_key(provider, model, lang, words)}.json"
    dirs = config.cache_dirs("SAHAYAK_MT_REPLAY", REPLAY_DIR, "mt")
    path = next((d / name for d in dirs if (d / name).exists()), REPLAY_DIR / name)
    if mode != "live" and path.exists():
        replies = json.loads(path.read_text(encoding="utf-8"))["replies"]
    elif mode == "replay" or not (key := os.environ.get(key_var)):
        return {}
    else:
        try:
            replies = _call_live(provider, model, key, lang, words)
        except Exception:  # network, quota, schema: the Glossary result stands
            return {}
        if mode == "record":
            out = config.cache_write_dir("SAHAYAK_MT_REPLAY", REPLAY_DIR, "mt")
            out.mkdir(parents=True, exist_ok=True)
            (out / name).write_text(json.dumps({"provider": provider, "model": model, "lang": lang,
                                        "words": words, "replies": replies},
                                       ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if len(replies) != len(words):  # misaligned reply: trust none of it
        return {}
    return {w: e for w, r in zip(words, replies, strict=True) if (e := _clean(r))}
