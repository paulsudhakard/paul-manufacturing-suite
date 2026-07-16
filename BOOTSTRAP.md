# Bootstrap — New Developer Setup (Under 5 Minutes)

This is the fast path. For branching conventions, engineering rules, and
code style, see `CONTRIBUTING.md`. For what the project is, see `README.md`.

## Prerequisites

- **Python 3.12+**
- **git**
- **Network access to PyPI** during `make setup` only (to fetch the pinned
  dev tools and the build backend). Nothing is fetched after that — `make
  lint`/`format`/`typecheck`/`test`/`ci` all run fully offline once `make
  setup` has completed once.

If you needed anything more than this, that's a bug in this document —
please report it.

## Steps

```bash
# 1. Clone (≈10s)
git clone <repo-url>
cd PMS

# 2. Install (≈30-60s) — creates .venv, installs the pinned dev tools
#    (pytest, black, ruff, mypy) and the core package itself, editable
make setup

# 3. Verify — run the exact job CI runs: lint → typecheck → test
make ci
```

If step 3 prints all-green, your environment is confirmed working and
matches CI exactly — you're ready to write code.

## What "green" looks like

- `ruff check .` — no errors
- `black --check .` — no files would be reformatted
- `mypy core` — no type errors
- `pytest` — 2 passed (the Sprint 0 environment-sanity test; more tests
  appear as later sprints add them)

## Available Commands

| Command | Does |
|---|---|
| `make setup` | Create `.venv`, install pinned dev tools + `core` (editable) |
| `make lint` | Check formatting and lint rules (does not modify files) |
| `make format` | Auto-fix formatting and lintable issues |
| `make typecheck` | Run mypy against `core/` |
| `make test` | Run the test suite (pytest) |
| `make ci` | `lint` + `typecheck` + `test` — exactly what CI runs |
| `make clean` | Remove `.venv` and all tool caches, back to a fresh checkout |

## Troubleshooting

- **`make: command not found`** — install `make` via your OS package
  manager (e.g. `apt install make`, `brew install make`); it is assumed
  present, same as `git`.
- **Wrong Python version picked up** — `python3 --version` must report
  3.12 or newer before running `make setup`; if not, point `python3` at a
  3.12+ interpreter (e.g. via `pyenv` or your OS's package manager) and
  re-run.
- **Started over from a broken state** — `make clean && make setup` always
  gets you back to a known-good environment; nothing outside `.venv` and
  tool caches is ever touched by either command.
- **`make setup` fails with `No matching distribution found for
  setuptools`** — this means `make setup` ran without PyPI access (see
  Prerequisites above). It needs network the first time only; once
  `.venv` is populated, every other command is fully offline.

## Confirming you're actually done

You've successfully bootstrapped when:
1. `make ci` exits with status 0 and shows no lint/type/test failures, and
2. `python3 -c "import core; print(core.__version__)"` (from within the
   activated `.venv`) prints `0.1.0`.

Both together are the complete Sprint 0 acceptance bar — if either fails,
the environment isn't ready yet.
