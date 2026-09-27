PY ?= python3
.PHONY: install check lint test eval web run

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
