PY ?= python3
.PHONY: install check lint test eval web smoke run corpus corpus-offline index

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

# Gate both paths: the keyless BM25 core must hold on its own, and so must hybrid.
eval:
	SAHAYAK_DENSE=0 $(PY) eval/run_eval.py --gate
	$(PY) eval/run_eval.py --gate
	# The MT fallback (replayed, no key, no network) must hold the same gates in both modes.
	SAHAYAK_MT=groq SAHAYAK_MT_REPLAY=replay SAHAYAK_DENSE=0 $(PY) eval/run_eval.py --gate
	SAHAYAK_MT=groq SAHAYAK_MT_REPLAY=replay $(PY) eval/run_eval.py --gate

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
	$(PY) corpus/fetch.py && $(PY) corpus/chunk.py && $(PY) -m api.retriever.dense build

corpus-offline:
	$(PY) corpus/fetch.py --offline && $(PY) corpus/chunk.py

# Rebuild the optional dense index after any re-chunk (~80 s on 2 vCPU for ~1.1k chunks).
index:
	$(PY) -m api.retriever.dense build
