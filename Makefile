.PHONY: setup lint format typecheck test ci

# Documented prerequisites (README.md): Python 3.12+, git. Nothing else.

setup:
	python3 -m venv .venv
	. .venv/bin/activate; pip install --upgrade pip
	. .venv/bin/activate; pip install -e ".[dev]"

lint:
	. .venv/bin/activate; ruff check .
	. .venv/bin/activate; black --check .

format:
	. .venv/bin/activate; black .
	. .venv/bin/activate; ruff check --fix .

typecheck:
	. .venv/bin/activate; mypy core

test:
	. .venv/bin/activate; pytest

# The single command CI runs, and the single command a new engineer runs
# locally to reproduce a CI failure exactly (Sprint 0 acceptance criterion).
ci: lint typecheck test
