#!/usr/bin/env python3
"""Start IP-SAKTI Sahayak. One command, any machine, any IDE.

    python run.py

Put a Gemini key in `.env` (copy `.env.example`) and the whole assistant runs online:
AI synthesis over the cited quotes, free-form Ayurveda chat, and machine translation of
unknown Hindi/Gujarati words. Put nothing there and the same command runs fully offline —
retrieval, the Status Ledger, the Answer Contract, the calculators and the Claim Sentry
all work with no key and no network.

This script only prepares and launches; all configuration lives in `api/config.py`.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "web" / "dist" / "index.html"


def _run(cmd: list[str], cwd: Path) -> bool:
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
        return True
    except (subprocess.CalledProcessError, OSError):
        return False


def ensure_python_deps() -> None:
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
        import yaml  # noqa: F401
    except ImportError:
        print("Installing Python dependencies (once)...", flush=True)
        _run([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"], ROOT)


def ensure_web_build() -> bool:
    """Build the web UI if it is missing. Returns False when only the API can be served."""
    if DIST.exists():
        return True
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm:
        print(
            "\n  Node.js was not found, so the chat interface cannot be built.\n"
            "  Install Node 20+ from https://nodejs.org and run this again.\n"
            "  The API itself will still start, and /health and /chat will answer.\n",
            flush=True,
        )
        return False
    web = ROOT / "web"
    if not (web / "node_modules").exists():
        print("Installing web dependencies (once, ~1 min)...", flush=True)
        if not _run([npm, "ci", "--silent"], web) and not _run([npm, "install", "--silent"], web):
            return False
    print("Building the web interface (once, ~10 s)...", flush=True)
    _run([npm, "run", "--silent", "build"], web)
    return DIST.exists()


def banner(url: str, has_ui: bool) -> None:
    from api import config  # imported here so `.env` is loaded by the package first

    c = config.summary()
    keys = ", ".join(c["keys_present"]) or "none"
    print("\n" + "=" * 68)
    print("  IP-SAKTI Sahayak")
    print("=" * 68)
    if c["mode"] == "online":
        print(f"  Mode          ONLINE  (keys found: {keys})")
        print(f"  Synthesis     {c['llm']}")
        print(f"  Ayurveda chat {c['chat']}")
        print(f"  Translation   {c['translation']}")
    else:
        print("  Mode          OFFLINE  (no API key found - everything still works)")
        print("  To go online  copy .env.example to .env and paste your GEMINI_API_KEY")
    print(f"  Interface     {url}" if has_ui else f"  API only      {url}/health")
    print("  Stop          Ctrl+C")
    print("=" * 68 + "\n", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Start IP-SAKTI Sahayak.")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-open", action="store_true", help="do not open a browser")
    args = ap.parse_args()

    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    ensure_python_deps()
    has_ui = ensure_web_build()

    url = f"http://localhost:{args.port}"
    banner(url, has_ui)
    if has_ui and not args.no_open:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    import uvicorn

    uvicorn.run("api.main:app", host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nStopped.")
