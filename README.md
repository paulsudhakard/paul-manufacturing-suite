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

## Running the Manufacturing Pipeline

`tools/run_svg_pipeline.py` is the official command-line entry point
for processing a real SVG artwork file through the full pipeline
(SVG Import → Geometry Validation → Geometry Repair → Manufacturing
Validation → Manufacturing Repair → Male Generator → Female Generator
→ Preview Generation → DXF Export → Validation Report). It's a thin
wrapper around `core.orchestration.orchestrator.run()` — it contains
no geometry or manufacturing logic of its own.

```bash
python tools/run_svg_pipeline.py \
    --input test_data/logo.svg \
    --output output
```

Options:

| Flag | Required | Description |
|---|---|---|
| `--input` | Yes | Path to the input SVG file |
| `--output` | Yes | Output directory (created automatically if missing) |
| `--debug` | No | Show a full stack trace on error instead of a short message |

Files written to `--output`:

| File | Contents |
|---|---|
| `pipeline.dxf` | RDWorks-ready DXF (male + female dies, registration/alignment marks) |
| `validation_report.json` | Geometry/manufacturing issues found, repair actions taken, and overall pass/fail |

If the artwork triggers manufacturing warnings that survive repair
(e.g. lines thinner than the configured minimum), the tool still exits
`0` and writes both files — `validation_report.json`'s `"passed"` field
reflects whether the *artwork* is clean, which is independent of
whether the *tool run* succeeded. A non-zero exit code means the tool
itself failed (bad input, malformed SVG, etc.), not that the seal
design has warnings.

See `docs/ORCHESTRATOR_SEQUENCE.md` for what each pipeline stage does.

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
