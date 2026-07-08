# Contributing to PMS

## Setup

```bash
make setup   # one command, per Sprint 0's acceptance criterion
make ci      # reproduces exactly what CI runs
```

Prerequisites: Python 3.12+, git. Nothing else — if you needed anything
more, that's a Sprint 0 bug, please report it.

## Branching Model

- **`main`** — always releasable; only receives merges from `develop` at a
  sprint boundary, or hotfixes.
- **`develop`** — integration branch; every sprint's work lands here first.
- **`feature/<short-description>`** — one branch per unit of work (typically
  one sprint, occasionally split further for review size), branched from
  `develop`, merged back via PR.

No direct commits to `main` or `develop` — everything goes through a PR
against `develop`, gated on a green `ci` job (`.github/workflows/ci.yml`).

## Commit Conventions

- Small, reviewable commits over one giant commit per sprint.
- Reference the sprint number in the PR title, e.g. `Sprint 3: CorelDRAW
  Adapter — health check round trip`.
- Update `CHANGELOG.md` under `[Unreleased]` as part of the same PR that
  introduces the change, not as a separate follow-up.

## Engineering Rules (carried from the Implementation Plan)

- No dead code, no TODOs, no speculative implementation of a later sprint's
  functionality (Implementation Plan, "How to Read This Plan").
- Where a later sprint needs to replace an earlier sprint's placeholder
  value, the earlier sprint takes it as an explicit caller-supplied
  parameter — never a hardcoded stand-in silently overwritten later.
- If implementing a sprint reveals a genuine contract gap in the frozen
  Architecture v3 / TDD v1, **flag it explicitly** (in the PR description
  and, if material, as an entry under "Findings" in the relevant sprint's
  section of `docs/ImplementationPlan_Sprints0-20.md`) rather than quietly
  patching around it.

## Code Style

- Formatting/linting/typing are enforced by `make lint` / `make typecheck`
  (black, ruff, mypy — see `pyproject.toml` for exact pinned versions).
- Adapter-side (VBA) standards: no manufacturing threshold, formula, or
  decision logic in any Adapter class, full stop (TDD §36) — Adapters are
  thin HTTP clients only.
- VBA source is committed as text-exported `.cls`/`.frm` files, never as a
  binary `.gms` project file — see `adapters/coreldraw/README.md`.
