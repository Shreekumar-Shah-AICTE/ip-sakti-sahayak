PY ?= python3
.PHONY: install check lint test eval web run corpus corpus-offline

install:
	$(PY) -m pip install -q -r requirements-dev.txt
	cd web && npm ci --silent

check: lint test eval web

lint:
	$(PY) -m ruff check .

test:
	$(PY) -m pytest -q

eval:
	$(PY) eval/run_eval.py --gate

# Type-check and build the web bundle (Playwright smoke test joins at M4).
web:
	cd web && npm run --silent build

run:
	./run.sh

# The Library: fetch + extract + chunk (needs network) / rebuild from local raw files.
corpus:
	$(PY) corpus/fetch.py && $(PY) corpus/chunk.py

corpus-offline:
	$(PY) corpus/fetch.py --offline && $(PY) corpus/chunk.py
