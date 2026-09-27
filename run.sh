#!/usr/bin/env sh
# Start IP-SAKTI Sahayak on one port. Works with no API keys.
set -e
cd "$(dirname "$0")"
PORT="${PORT:-8000}"
# Optional keys live in a git-ignored .env, loaded by the api package itself (api/config.py).

python3 -c "import fastapi, uvicorn, yaml" 2>/dev/null || python3 -m pip install -q -r requirements.txt
if [ ! -d web/dist ] && command -v npm >/dev/null 2>&1; then
  (cd web && npm ci --silent && npm run --silent build) || echo "web build skipped; API only"
fi
exec python3 -m uvicorn api.main:app --host 0.0.0.0 --port "$PORT"
