.PHONY: setup lint format typecheck test ci clean

# Documented prerequisites (README.md, BOOTSTRAP.md): Python 3.12+, git.
# Nothing else. Every target below assumes `make setup` has already run.

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
	. .venv/bin/activate; mypy core adapters

test:
	. .venv/bin/activate; pytest

# The single command CI runs, and the single command a new engineer runs
# locally to reproduce a CI failure exactly (Sprint 0 acceptance criterion).
ci: lint typecheck test

# Removes everything `setup` creates plus tool caches — a new engineer (or
# a CI runner) can always get back to a truly fresh state with one command.
clean:
	rm -rf .venv
	rm -rf .mypy_cache .ruff_cache .pytest_cache
	rm -rf *.egg-info core.egg-info build dist
	find . -type d -name "__pycache__" -not -path "./.git/*" -exec rm -rf {} +
