# PMS — Embossing Seal Manufacturing Pipeline

A working pipeline that takes seal artwork through validation, repair,
Male/Female die generation, and DXF export for laser cutting (RDWorks-
compatible).

## Status

**MVP complete, prepared for handover.** Read
**`docs/ENGINEERING_HANDOVER.md` first** — it explains how this
diverged from the original planning documents, what's verified vs.
assumed, dependency tree, known limitations, and remaining work before
real production use.

The following are frozen planning inputs, kept for historical/
architectural reference (see the handover doc for how the actual build
diverged from them):

- `docs/Architecture_v3.md`
- `docs/TechnicalDesignDocument_v1.md`
- `docs/ImplementationPlan_Sprints0-20.md`

## Quick Start

Prerequisites: **Python 3.12+**, **git**, network access (first run only).

```bash
git clone <repo-url>
cd PMS
make setup   # creates .venv, installs pinned dev tooling + the core package
make ci      # lint + typecheck + test — the exact job CI runs
```

See `BOOTSTRAP.md` for a full under-5-minutes walkthrough.

## Try the pipeline

```python
from core.engines.geometry.model import Circle, Point
from core.engines.manufacturing.pipeline import run_pipeline
from core.engines.manufacturing.rules import RuleSet

result = run_pipeline(Circle(Point(0, 0), 20), RuleSet.load_default())
print(result.dxf_text)  # RDWorks-ready DXF text
```

## Repository Layout

```
core/
  api/                Core HTTP API (stdlib WSGI)
  config/ logging/ exceptions/ events/    Core Skeleton
  geometry/           Neutral Geometry Format (wire format)
  jobs/               interim in-memory job store
  engines/geometry/   Geometry Engine (2D CAD kernel) — frozen
  engines/manufacturing/   Manufacturing Engine — validator, repair,
                           Male/Female generator, DXF export
  tests/              unit, integration, regression suites
adapters/coreldraw/    reference Adapter client (Python stand-in for VBA)
products/              Product Definition scaffolding (not populated —
                        the plugin system was never built, see handover doc)
docs/                  frozen planning docs + ENGINEERING_HANDOVER.md
```

## Contributing

See `CONTRIBUTING.md` for the branching model and engineering rules
(most importantly: never patch a specific logo/artwork — always
improve the generic algorithm, then add a regression fixture).
