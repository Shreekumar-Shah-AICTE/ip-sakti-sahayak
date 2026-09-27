PY ?= python3
.PHONY: install check lint test eval web smoke run corpus corpus-offline

install:
	$(PY) -m pip install -q -r requirements-dev.txt
	cd web && npm ci --silent
	# Browser for the smoke test; skipped if a system Chromium is set via CHROMIUM_PATH.
	[ -n "$$CHROMIUM_PATH" ] || $(PY) -m playwright install --with-deps chromium

check: lint test eval web smoke

lint:
	$(PY) -m ruff check .

test:
	$(PY) -m pytest -q

eval:
	$(PY) eval/run_eval.py --gate

# Type-check and build the web bundle.
web:
	cd web && npm run --silent build

# Playwright smoke test: real browser, real API, keyless (needs the web build).
smoke:
	$(PY) -m pytest -q smoke

run:
	./run.sh

# The Library: fetch + extract + chunk (needs network) / rebuild from local raw files.
corpus:
	$(PY) corpus/fetch.py && $(PY) corpus/chunk.py

corpus-offline:
	$(PY) corpus/fetch.py --offline && $(PY) corpus/chunk.py
