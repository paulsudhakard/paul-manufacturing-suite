# Engineering Documentation — Handover

Status: MVP implementation phase complete. This document is the single
place a new engineer should read first — it consolidates what was
actually built, how it diverges from the original frozen planning
documents (`docs/Architecture_v3.md`, `docs/TechnicalDesignDocument_v1.md`,
`docs/ImplementationPlan_Sprints0-20.md`), what's verified, and what's
still outstanding.

## 1. How the project actually evolved vs. the original plan

The three documents in `docs/` were frozen as authoritative and
Sprints 0–1 were built exactly against them (Core Skeleton: config,
logging, exception hierarchy, event bus). From Sprint 2 onward, the
project's actual objective changed direction (documented in-conversation,
not in a revised planning doc): away from the full 20-sprint enterprise
platform (Workflow Engine, Plugin Engine, Queue Manager, Enterprise
Services, Notifications) and toward the fastest path to a working
embossing-seal manufacturing pipeline. **None of the deferred systems
below were built**, by deliberate, repeated instruction — this is a
scope decision, not an oversight:

- Workflow Engine, Plugin Engine / Product Definition loader
- Queue Manager, Notification Engine
- Enterprise Services (Operators/Customers/Licensing beyond a stub)
- Template Engine, Asset Management Engine
- Extension SDK (any tier)
- AI Recommendation Engine, embossability scoring
- Reporting Engine (PDF/report generation)

What exists instead, in build order:

1. **Core Skeleton** (`core/config`, `core/logging`, `core/exceptions`,
   `core/events`) — built per the original TDD, unchanged in approach.
2. **Communication Pipeline** (`core/api`, `core/geometry`,
   `core/jobs`, `adapters/coreldraw/reference_client`) — a hand-rolled
   stdlib WSGI API (not FastAPI/Starlette — unavailable to install in
   the build sandbox; see §4), the Neutral Geometry Format wire model,
   and a Python reference Adapter client used in place of the real VBA
   client for automated testing.
3. **Geometry Engine** (`core/engines/geometry`) — a from-scratch 2D
   CAD kernel: primitives (Line/Arc/Bezier/Circle/Ellipse/Polygon/
   CompoundPath), transforms, bounding boxes, winding/fill-rule tests,
   curve flattening/simplification/smoothing, measurement (area/
   perimeter/centroid), polygon offset, boolean *preparation* (not full
   CSG — see §3), structural validation, deterministic repair, and
   NeutralGeometry/DXF import-export. **Frozen** after reaching this
   scope — no further generic-CAD investment unless it blocks
   manufacturing.
4. **Manufacturing Engine** (`core/engines/manufacturing`) — built on
   top of the frozen Geometry Engine: config-driven Rule Engine,
   manufacturing Validator, deterministic Repair, Male/Female Die
   Generator, Preview/diff bundle, DXF export, RDWorks layer mapping,
   and the end-to-end `pipeline.py`.
5. **Regression suite** (`core/tests/regression/manufacturing`) — 16
   synthetic, generic fixtures standing in for real production artwork,
   which has not yet been supplied (see §5).

## 2. What's verified, and how

Every claim below was actually executed in the build environment, not
asserted from reading the code:

- **131 test cases** (unit + integration + regression) pass, run via a
  manual test-execution harness because `pytest` itself is not
  installable in the build sandbox (no network access — the *only*
  thing this affects; the test code itself is ordinary pytest and will
  run normally via `pytest` wherever network access exists, e.g. real CI).
- **Every module under `core/` and `adapters/` imports cleanly** —
  verified via `pkgutil.walk_packages` + `importlib.import_module` over
  every discovered module, not spot-checked.
- **A real wheel was built and installed** into an isolated virtualenv
  (not editable, not sys.path tricks) and the full manufacturing
  pipeline was run from the installed package. This caught a real
  packaging bug (see CHANGELOG 0.4.0) that editable-install testing had
  masked throughout earlier development.
- **DXF output was structurally validated** (group-code pairing,
  SECTION/ENDSEC balance, valid entity types) but **never opened in
  real RDWorks or any DXF viewer** — no such software is available in
  this environment. This is the most important outstanding
  verification gap before production use.
- Every numeric default in `core/engines/manufacturing/config/default_rules.yaml`
  is a first-draft engineering judgment, not a physically validated
  constant — see §5.

## 3. Known limitations (by design, not oversight)

- **No full polygon boolean operations** (union/intersection/
  difference). `boolean_prep.py` provides intersection-finding and
  inside/outside classification — the documented *input* to a future
  boolean engine, not the algorithm itself. Real CSG (Weiler-Atherton,
  Vatti, etc.) is a substantial standalone project.
- **Polygon offset is a "naive" per-edge-normal algorithm**, exact for
  convex shapes, without self-intersection trimming for concave/
  over-shrunk cases.
- **Manufacturing checks needing true topology (weak bridges, thin
  lines, floating geometry) are deterministic proxies**, not exact
  topological solvers — each is documented in
  `core/engines/manufacturing/analysis_utils.py` and `validator.py`
  with its specific method and failure mode. One serious proxy bug
  (false-positive on every circle) was found and fixed during this
  phase — see CHANGELOG 0.3.0 — a concrete illustration of why these
  proxies need continued adversarial testing against real artwork.
- **DXF export is minimal**: LINE/ARC/CIRCLE entities only, no BLOCKS,
  no full R12+ feature set.
- **No real VBA Adapter code exists** despite the documented
  convention in `adapters/coreldraw/README.md` — the project moved to
  a Python reference client before real CorelDRAW-side work began.
- **Clearance/kerf/material-compensation formula
  (`male_female.py`) is unvalidated** — first-draft engineering
  judgment pending real laser/material testing.
- **`thin_line` warnings have no dedicated corrective repair** — only
  detection exists.
- No Queue/Workflow/Enterprise/Reporting/Notification/Plugin systems —
  see §1.

## 4. Dependency tree

### Runtime (`[project.dependencies]`)
```
pyyaml==6.0.2        # config.yaml / manufacturing rule YAML loading
```
That's it — the Core API, Geometry Engine, and Manufacturing Engine
are otherwise **pure Python 3.12 standard library** (dataclasses, math,
json, wsgiref, http.server). This was a deliberate choice:
FastAPI/Starlette/Pydantic were not installable in the build sandbox
(no PyPI access), and a stdlib WSGI implementation turned out to be
entirely adequate at this project's actual scale.

### Dev-only (`[project.optional-dependencies].dev` / `requirements-dev.txt`)
```
pytest==8.3.4      # test runner
black==24.10.0     # formatter
ruff==0.8.4        # linter
mypy==1.13.0       # type checker
requests==2.32.3   # reference Adapter client + its tests only
```

### Build backend
```
setuptools>=68     # via [build-system]
```

No other external dependency exists anywhere in the codebase. Verified
by grepping every `import`/`from` statement across `core/` and
`adapters/` against this list — nothing unaccounted for.

## 5. Remaining work before real production use

In priority order:

1. **Validate against real production artwork.** Everything is
   currently tested against synthetic, generic fixtures. This is the
   single largest gap — the regression suite exists specifically to
   grow as real logos are supplied and processed (per the engineering
   rule: fix the generic algorithm, never patch a specific logo, then
   pin the artwork as a permanent regression test).
2. **Open a generated DXF in real RDWorks** and confirm import,
   layer/color-to-parameter mapping, and geometry fidelity. The
   `rdworks_layers.py` color convention is explicitly flagged as
   needing operator confirmation.
3. **Physically validate the clearance/kerf/material-compensation
   formula** against an actual laser cut and real seal material.
4. **Add a corrective repair for `thin_line` warnings** (currently
   detection-only).
5. **Real CorelDRAW VBA Adapter** — the reference Python client proved
   the communication contract; the real VBA implementation (per
   `adapters/coreldraw/README.md`'s documented but unused convention)
   still needs to be written and tested inside actual CorelDRAW.
6. Decide whether any of the deferred systems (§1) are actually needed
   for production use (e.g. a Queue Manager once multi-operator use is
   real) — none are currently blocking a single-operator pipeline.

## 6. Explicit TODO items

None marked in code (`grep -rn "TODO\|FIXME"` across the whole
repository returns nothing — verified during handover). The items
below are architecturally-known gaps, tracked here instead of as code
comments since none block current functionality:

- SVG import/export was scoped in early planning for the Geometry
  Engine but was not built before the project's focus moved to the
  Manufacturing Engine — only NeutralGeometry (JSON) and DXF
  import/export exist.
- DXF *import* (reading third-party DXF files) does not exist — only
  export.
- No `docs/ProductDefinitionAuthoringGuide.md` — moot, since the
  Plugin/Product Definition system itself was never built (§1).
