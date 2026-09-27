"""IP-SAKTI Sahayak — FastAPI entry point.

Keyless by design: with no API keys set, the app starts and serves the
extractive core. LLM and translation providers are optional adapters.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

VERSION = "0.0.1"
ROOT = Path(__file__).resolve().parent.parent
WEB_DIST = ROOT / "web" / "dist"

# Optional adapters, detected by environment-variable *name* only.
# Values are never read into responses or logs.
OPTIONAL_ADAPTERS = {
    "llm.gemini": "GEMINI_API_KEY",
    "llm.groq": "GROQ_API_KEY",
    "mt.sarvam": "SARVAM_API_KEY",
    "mt.bhashini": "BHASHINI_API_KEY",
}

app = FastAPI(title="IP-SAKTI Sahayak", version=VERSION)


def adapter_status() -> dict[str, bool]:
    """Which optional adapters are configured (True/False only, never the value)."""
    return {name: bool(os.environ.get(var)) for name, var in OPTIONAL_ADAPTERS.items()}


@app.get("/health")
def health() -> dict:
    adapters = adapter_status()
    return {
        "status": "ok",
        "version": VERSION,
        "mode": "keyless" if not any(adapters.values()) else "adapters",
        "adapters": adapters,
    }


if WEB_DIST.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
