# Changelog

All notable changes to this project are documented here.
Format loosely follows [Keep a Changelog](https://keepachangelog.com/).
Versioning: `core`'s own package version (`core/__init__.py`) advances
independently from the API version (`/v1`, `/v2`, ...), the ProductDefinition
versions, and the WorkflowDefinition versions — see TDD §25.

## [Unreleased]

Nothing yet.

## [0.4.0] — Handover Preparation

### Fixed (packaging correctness, discovered during handover verification)
- `pyproject.toml`: `packages = ["core"]` only shipped the top-level
  package in a real (non-editable) build — verified by building an
  actual wheel, which contained 2 files instead of 67. Switched to
  `[tool.setuptools.packages.find]` with automatic subpackage discovery
  and explicit test exclusion. Re-verified: built wheel now contains
  every real module plus the manufacturing config YAML (via
  `package-data`), installs cleanly into an isolated venv, and runs the
  full pipeline from the installed package (not the source tree).
- `ruff` was excluding all of `adapters/` (including real, non-VBA
  Python code in `reference_client/`) — narrowed to exclude only
  `products/` (genuinely non-Python).
- `mypy` only checked `core`; now also checks `adapters`.
- `requirements-dev.txt` had drifted from `pyproject.toml`'s dev extras
  (missing `requests`) — resynced.
- Added explicit `__init__.py` to `core/engines/`, `core/tests/`,
  `core/tests/unit/`, `core/tests/integration/`, `core/tests/regression/`
  — these worked via implicit namespace packages, but explicit
  initialization removes any ambiguity for a new team taking this over.

### Notes
- No new functionality in this entry — verification and packaging only.
- Known gap: `adapters/coreldraw/README.md` documents a VBA `.cls`/`.frm`
  text-export convention, but no VBA code was ever written — the project
  pivoted to a Python reference Adapter client
  (`adapters/coreldraw/reference_client/`) for automated testing before
  real CorelDRAW-side work began. Real VBA implementation remains
  outstanding.

## [0.3.0] — Manufacturing Engine

### Added
- Manufacturing Rule Engine (`core/engines/manufacturing/rules.py`):
  config-driven `RuleSet`, zero hardcoded thresholds, loaded from
  `config/default_rules.yaml`.
- Manufacturing Validator: thin lines, tiny holes/islands, floating/
  disconnected geometry, weak bridges, sharp corners, min spacing, node
  density — all threshold-driven.
- Manufacturing Repair: deterministic only (remove tiny holes, merge
  tiny islands via keyhole splice, round sharp corners, widen weak
  bridges), with an action log and area/perimeter similarity score.
- Male/Female Die Generator, relief generation, registration/alignment
  marks.
- Manufacturing Preview (Original/Repaired/Male/Female bundle + diff
  metrics).
- Minimal DXF exporter (LINE/ARC/CIRCLE entities) and RDWorks layer/
  color mapping.
- End-to-end pipeline (`pipeline.py`): Import -> Validate -> Repair ->
  Male -> Female -> Compare -> DXF as one `run_pipeline()` call.
- Regression suite: 16 synthetic seal-category fixtures (generic/
  original geometry, not reproductions of real trademarks).

### Fixed (generic algorithm corrections, found via the regression suite)
- `neutral_io.py`: closed paths got a duplicate closing node on export,
  breaking round-trip fidelity for every closed shape.
- `analysis_utils.py`: hole vs. island classification used containment
  alone, misclassifying same-winding islands as holes — fixed to also
  require opposite winding.
- `validator.py`: erosion-based thin-line detection could silently
  invert past a shape's own width — replaced with the edge-distance
  proxy already verified for weak-bridge detection.
- `analysis_utils.py` `min_self_distance`: false-positive weak-bridge/
  thin-line warnings on every circle/curve, from mistaking tessellation-
  adjacent edges for narrow necks — fixed via an arc-length-vs-
  straight-distance ratio guard.

## [0.2.0] — Communication Pipeline

### Added
- Core HTTP API (stdlib WSGI): health, version, job submission,
  structured `ErrorResponse` envelope, local bearer-token auth,
  idempotency support.
- Neutral Geometry Format: data model, serialization, interface-level
  structural validation, round-trip contract helper.
- Reference Adapter client (Python stand-in for the eventual VBA
  client) with retry logic and typed error mapping.
- End-to-end integration test: simulated CorelDRAW export -> Core ->
  validate -> response -> round-trip check, over a real HTTP server.

## [0.1.0] — Sprint 0 + Sprint 1

### Added
- Repository scaffold per Architecture v3 §3 / TDD §34 folder structure.
- `core` package skeleton with a reported version, importable from a
  fresh clone with no manual setup.
- Pinned dev tooling (`pyproject.toml` dev extra + `requirements-dev.txt`).
- CI pipeline (`.github/workflows/ci.yml`): lint + typecheck + test,
  gated on every push/PR.
- `make setup` / `make ci` / `BOOTSTRAP.md` as the developer bootstrap path.
- Git branching model documented (`CONTRIBUTING.md`).
- VBA project export convention documented (`adapters/coreldraw/README.md`)
  — see the 0.4.0 note above: this convention was never actually used.
- Core Skeleton: configuration loading, structured logging, full
  `PlatformException` hierarchy, in-process Event Bus.
- Environment-sanity test confirming `core` imports cleanly and reports
  a well-formed version string.
