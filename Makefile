# creature-forge — Linux/AMD target. All logic lives in tasks.py so the gate is
# identical on Windows (see make.ps1). Override PY to point at your venv python.
PY ?= python3

.PHONY: setup run verify schemas test clean

setup:
	$(PY) tasks.py setup

run:
	$(PY) tasks.py run $(ARGS)

verify:
	$(PY) tasks.py verify

schemas:
	$(PY) tasks.py schemas

test:
	$(PY) tasks.py test

clean:
	$(PY) tasks.py clean
