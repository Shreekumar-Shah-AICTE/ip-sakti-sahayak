"""IP-SAKTI Sahayak API package.

Importing the package loads `.env` from the repo root, so every entry point — `run.py`,
`uvicorn api.main:app`, an IDE run button, pytest — sees the same configuration without
anyone having to remember to export a variable.
"""

from api.config import load_env as _load_env

_load_env()
