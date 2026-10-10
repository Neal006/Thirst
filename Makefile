# Thirst task runner (plan step 1.3.e). On Windows without make, run the commands directly or use Git Bash.
PY ?= python
API ?=
PYTEST = $(PY) -m pytest -m "not gpu and not aws"

.PHONY: test cov cov-engine lint type check fixtures assumptions build deploy web web-test smoke skeleton

test:
	$(PYTEST)

cov:
	$(PYTEST) --cov --cov-report=term-missing

# Engine coverage gate (>= 90). Skipped until the first engine test file exists.
cov-engine:
	@if ls tests/engine/test_*.py >/dev/null 2>&1; then \
		$(PYTEST) tests/engine --cov=src/engine --cov-fail-under=90 --cov-report=term-missing; \
	else echo "cov-engine: no engine tests yet, skipping"; fi

lint:
	$(PY) -m ruff check .

type:
	$(PY) -m mypy

check: lint type cov cov-engine

skeleton:
	$(PY) scripts/check_skeleton.py

fixtures:
	$(PY) scripts/gen_fixtures.py

assumptions:
	$(PY) scripts/gen_assumptions.py

build:
	sam build --use-container

deploy:
	sam deploy

web:
	cd web && npm run dev

web-test:
	cd web && npm test -- --run

smoke:
	bash scripts/smoke.sh "$(API)"
