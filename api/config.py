"""One switch for the whole app: offline by default, online the moment a key exists.

The promise this module keeps (KERNEL §2): clone the repo anywhere, put a key in `.env`,
and every optional adapter turns on together. Put no key anywhere and the same code path
runs fully offline, with no network call and no behaviour change beyond the extras being
absent. Nothing here ever reads a key *value* into a return value, a log or a response.

Resolution order, highest first:
1. An explicit environment variable (`SAHAYAK_LLM=groq`, `SAHAYAK_MODE=offline`, ...).
2. `.env` in the repo root, loaded once at import — the file the user is told to edit.
3. These defaults: offline unless a provider key is present, then online with Gemini first.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"

# Every key that can switch the app online, and the provider it belongs to.
PROVIDER_KEYS = ("GEMINI_API_KEY", "GROQ_API_KEY", "SARVAM_API_KEY")

# Preference order when nothing is pinned. Gemini first: it is the key the README asks for.
LLM_ORDER = (("gemini", "GEMINI_API_KEY"), ("groq", "GROQ_API_KEY"))
MT_ORDER = (("gemini", "GEMINI_API_KEY"), ("groq", "GROQ_API_KEY"), ("sarvam", "SARVAM_API_KEY"))


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def load_env(path: Path | None = None) -> list[str]:
    """Load `KEY=VALUE` lines from `.env` into the environment. Returns the names set.

    A real environment variable always wins, so a shell export or a CI setting is never
    silently overwritten by a file on disk. Returns names only — never values — so the
    result is safe to print. Offline mode skips the file entirely: "offline" has to mean
    offline even on a machine whose `.env` is full of keys.
    """
    if os.environ.get("SAHAYAK_MODE", "").lower() == "offline":
        return []
    path = path or ENV_PATH
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    loaded = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip().removeprefix("export ").strip()
        value = _strip_quotes(value)
        if not name or not value or name in os.environ:
            continue
        os.environ[name] = value
        loaded.append(name)
    return loaded


def mode() -> str:
    """"online" or "offline" — the single fact every adapter below agrees on."""
    pinned = os.environ.get("SAHAYAK_MODE", "auto").lower()
    if pinned in ("online", "offline"):
        return pinned
    return "online" if any(os.environ.get(k) for k in PROVIDER_KEYS) else "offline"


def online() -> bool:
    return mode() == "online"


def _resolve(order: tuple[tuple[str, str], ...], pinned: str | None) -> str | None:
    """Which provider this adapter should use, or None to stay off.

    An explicitly named provider is always honoured, online or not: naming one is how the
    replayed recordings are exercised with no key and no network. Only the *automatic*
    choice is gated on being online, so a machine with no key never reaches for a network.
    """
    pinned = (pinned or "auto").lower()
    if pinned in ("", "none"):
        return None
    if pinned != "auto":
        return pinned
    return next((name for name, key in order if os.environ.get(key)), None) if online() else None


def llm_provider() -> str | None:
    """Provider for the synthesis layer (M7), or None when it should stay off."""
    return _resolve(LLM_ORDER, os.environ.get("SAHAYAK_LLM"))


def mt_provider() -> str | None:
    """Provider for the Glossary's unknown-word translation, or None."""
    return _resolve(MT_ORDER, os.environ.get("SAHAYAK_MT"))


# Answers recorded on *this* machine while online. Git-ignored (under var/), so a user's
# own cache never dirties their clone; the committed fixtures stay the eval's ground truth.
USER_CACHE = ROOT / "var" / "cache"


def chat_provider() -> str | None:
    """Provider for free-form Ayurveda chat, or None (offline, or no key)."""
    return _resolve(LLM_ORDER, os.environ.get("SAHAYAK_CHAT_LLM"))


def replay_mode(var: str) -> str:
    """"record" online, "replay" offline — unless the caller pinned it in the environment.

    `replay` reads the recorded cache and never opens a socket, so the default offline is
    the guarantee that an unconfigured clone makes no network call. Online defaults to
    `record` (cache first, then live, then save): the free Gemini tier allows ~20 requests
    a day per model, so a demo that re-asks its questions must not spend quota twice, and a
    repeated question comes back instantly. A deliberate pin (`SAHAYAK_LLM_REPLAY=live`)
    is still obeyed: that is an instruction, not an accident.
    """
    pinned = os.environ.get(var, "").lower()
    if pinned in ("replay", "record", "live"):
        return pinned
    return "record" if online() else "replay"


def cache_dirs(var: str, committed: Path, name: str) -> list[Path]:
    """Where recorded answers are read from.

    Online, only this machine's own cache counts: the committed fixtures were recorded by
    whatever model the eval was built with, and letting them shadow the live model would
    mean a user with a working key sees last month's answer (or its "INSUFFICIENT") forever.
    Offline, or when a developer pinned a replay mode, exactly the committed fixtures count,
    so the test suite and the eval gates never see a user's cache.
    """
    if os.environ.get(var, "").lower() in ("replay", "record", "live") or not online():
        return [committed]
    return [USER_CACHE / name]


def cache_write_dir(var: str, committed: Path, name: str) -> Path:
    """Where a new recording goes: the committed fixtures only when a developer pinned
    record mode on purpose (that is how fixtures are authored), else the user cache."""
    return committed if os.environ.get(var, "").lower() == "record" else USER_CACHE / name


def summary() -> dict:
    """Safe-to-print picture of how this process is configured. Names and flags only."""
    return {
        "mode": mode(),
        "llm": llm_provider() or "none",
        "chat": chat_provider() or "none",
        "translation": mt_provider() or "none",
        "keys_present": sorted(k for k in PROVIDER_KEYS if os.environ.get(k)),
        "env_file": str(ENV_PATH) if ENV_PATH.exists() else None,
    }
