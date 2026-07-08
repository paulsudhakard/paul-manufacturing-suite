# PMS — Platform Manufacturing Suite

A product-independent manufacturing automation platform. Core knows about
geometry, rules, machines, materials, workflows, and jobs — it does not know
what an "embossing seal" or a "rubber stamp" *is*. That knowledge lives
entirely in pluggable Product Definitions under `products/`.

## Status

**Sprint 0 of 20 — Development Environment.** No engines, no API, no
product logic exist yet. This sprint only proves the repository builds,
lints, and runs its (currently near-empty) test suite cleanly.

The following documents are **frozen** and authoritative. This repository
implements them one sprint at a time, never ahead of the current sprint:

- `docs/Architecture_v3.md` — system architecture and design rationale
- `docs/TechnicalDesignDocument_v1.md` — schemas, contracts, API shape
- `docs/ImplementationPlan_Sprints0-20.md` — the sprint-by-sprint build order

## Quick Start

Prerequisites: **Python 3.12+**, **git**. Nothing else.

```bash
git clone <repo-url>
cd PMS
make setup   # creates .venv, installs pinned dev tooling + the core package
make ci      # lint + typecheck + test — the exact job CI runs
```

A green `make ci` locally means CI will be green too.

## Repository Layout

```
core/        product-blind engines, API, and contracts (Python)
products/    Product Definitions + plugin code (data + product-specific logic)
adapters/    CAD/UI adapters (CorelDRAW VBA today; contract admits others later)
docs/        architecture, SRS, and authoring guides
```

See each folder's `README.md` for what belongs there and when it arrives
(most engine folders are currently empty — check the Implementation Plan
for which sprint populates them).

## Contributing

See `CONTRIBUTING.md` for the branching model and commit conventions.
