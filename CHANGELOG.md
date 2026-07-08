# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).
Versioning: `core`'s own package version (`core/__init__.py`) advances
independently from the API version (`/v1`, `/v2`, ...), the ProductDefinition
versions, and the WorkflowDefinition versions — see TDD §25.

## [Unreleased]

Nothing yet — Sprint 1 begins here.

## [0.1.0] — Sprint 0: Development Environment

### Added
- Repository scaffold per Architecture v3 §3 / TDD §34 folder structure.
- `core` package skeleton (`core/__init__.py`) with a reported version,
  importable from a fresh clone with no manual setup.
- Pinned dev tooling (`pyproject.toml` dev extra + `requirements-dev.txt`):
  pytest 8.3.4, black 24.10.0, ruff 0.8.4, mypy 1.13.0.
- CI pipeline (`.github/workflows/ci.yml`): lint (ruff, black) + typecheck
  (mypy) + test (pytest), gated on every push/PR.
- `make setup` / `make ci` as the two documented commands a new engineer
  needs.
- Git branching model documented (`CONTRIBUTING.md`): `main` / `develop` /
  `feature/*`.
- VBA project export convention documented (`adapters/coreldraw/README.md`):
  `.cls`/`.frm` committed as text, never a binary `.gms`.
- Single environment-sanity test (`core/tests/unit/test_environment_sanity.py`):
  confirms `core` imports cleanly and reports a well-formed version string.

### Notes
- No engines, API routes, or product logic exist yet — every populated
  folder outside `core/__init__.py` and its test contains only a `README.md`
  stating what arrives, and in which sprint, per the Implementation Plan.
