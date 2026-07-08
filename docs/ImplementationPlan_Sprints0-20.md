# PMS — Implementation Plan (Sprints 0–20)
### Engineering Plan, Not Architecture — Vertical Slices Toward a Working Product

**Status:** Planning only, per your instruction — no code in this document. Architecture v3 and TDD v1 are treated as frozen inputs; where a sprint reveals a genuine contract gap, it's called out explicitly rather than patched silently (Engineering Rule 10).

---

## How to Read This Plan

Every sprint below follows the same structure you specified: Goal, Functional Requirements, Technical Tasks, Folder Changes, New Interfaces, New Classes, API Endpoints, Unit Tests, Integration Tests, Acceptance Criteria, Risks, Deliverables, Demo Scenario.

Two design principles I applied consistently to satisfy Engineering Rules 5–8 (no dead code, no TODOs, no speculative implementation):
- **Wherever a later sprint would need to replace an earlier sprint's placeholder** (e.g., Validation Engine needing rule thresholds before the Rule Engine exists), the earlier sprint takes that value as an explicit caller-supplied parameter rather than hardcoding it. The later sprint becomes "the real caller," not a rewrite — no throwaway code at any point.
- **Wherever architecture deferred a module** (Template Engine, Asset Management, Extension SDK Tier 3), sprints that would naturally use it instead route through the specific plugin's own code, exactly as v3 §8.3 intends product-specific behavior to work. This is called out explicitly in Sprints 14 and 18 below.

---

## Sprint 0 — Development Environment

**Sprint Goal:** A fresh clone builds, lints, and runs an empty test suite successfully on both the Core (Python) and Adapter (VBA) sides.

**Functional Requirements:** None (infrastructure only).

**Technical Tasks:**
- Scaffold the repository per TDD §34's folder structure (`core/`, `adapters/coreldraw/`, `docs/`, `products/_template/`).
- Set up Python environment/dependency management for Core (versions pinned).
- Configure linters/formatters/type-checker for Core (per TDD §36).
- Set up CI pipeline: lint + empty-test-suite job, gated on every commit.
- Establish git branching model (v2 §14: `main`/`develop`/`feature/*`) and `CHANGELOG.md` seed.
- Establish the VBA project export convention (`.cls`/`.frm` as text in git, not trapped in a binary `.gms` — v2 §14) even though no VBA code exists yet.

**Folder Changes:** Create the full top-level tree from TDD §34; every folder gets a `.gitkeep` or a README stating its intended contents (not a placeholder implementation — documentation, not code).

**New Interfaces:** None.

**New Classes:** None.

**API Endpoints:** None.

**Unit Tests:** A single "environment sanity" test confirming the Core package imports cleanly and reports its version.

**Integration Tests:** CI pipeline runs green end-to-end (lint + sanity test) on a fresh clone.

**Acceptance Criteria:** A new engineer can clone the repo and, with one documented command, get a green CI run with zero manual setup steps beyond documented prerequisites.

**Risks:** Tooling version drift across developer machines — mitigated by pinning versions in a lockfile from day one.

**Deliverables:** Repository scaffold, CI config, `CONTRIBUTING.md`, `CHANGELOG.md`.

**Demo Scenario:** Show a clean clone → one setup command → green CI badge, with the folder tree matching TDD §34.

---

## Sprint 1 — Core Skeleton

**Sprint Goal:** The Core process starts as a standalone executable, loads configuration, logs structured output, and demonstrates its exception hierarchy actually being thrown and classified correctly — with no HTTP layer yet.

**Functional Requirements:** Core starts, loads config per precedence order (TDD §20), and shuts down cleanly.

**Technical Tasks:**
- Implement Configuration loading (TDD §20): defaults → file → env → (no per-job override yet, since Jobs don't exist).
- Implement structured Logging (TDD §19): rotating file output, `LogEntry` shape enforced.
- Implement the full Exception Hierarchy (TDD §18) as real, throwable/catchable types — not stubs; a deliberate self-test throws one of each leaf exception and confirms correct classification.
- Implement the in-process Event Bus skeleton (TDD §32) with publish/subscribe, exercised by a logging subscriber (the only real subscriber this sprint).

**Folder Changes:** `core/config/`, `core/logging/`, `core/exceptions/`, `core/events/`, `core/main` entrypoint.

**New Interfaces:** Configuration loader contract; Logger facade contract; Event Bus publish/subscribe contract.

**New Classes:** `CoreConfig`, `ConfigLoader`, `LogWriter`, `EventBus`, full `PlatformException` hierarchy (TDD §18).

**API Endpoints:** None (deliberately — API arrives in Sprint 2, so this sprint proves the skeleton works independent of HTTP).

**Unit Tests:** Config precedence resolution (each override level tested independently and in combination); every exception type correctly reports its `category` (TDD §17.2); Event Bus delivers to all subscribers at least once.

**Integration Tests:** Process starts → loads config → logs a startup line → deliberately raises and logs one exception of each category → exits cleanly with code 0.

**Acceptance Criteria:** Running the Core executable from a terminal produces a correctly-classified log line for a forced test exception, with no crash and a clean exit.

**Risks:** Over-building the Event Bus before there's a real publisher (Sprint 2+) — mitigated by keeping it deliberately minimal (in-process only, no external broker, per TDD §32).

**Deliverables:** A runnable Core skeleton binary with passing tests.

**Demo Scenario:** Run Core from the command line; show the log file; show a forced `PluginConformanceException` correctly logged with its category and correlation ID.

---

## Sprint 2 — Core API

**Sprint Goal:** Core is reachable over HTTP on `127.0.0.1`, authenticates requests via the local bearer token, and returns a correctly-shaped health response.

**Functional Requirements:** TDD §29 authentication flow; `/v1/health`.

**Technical Tasks:**
- Stand up the API framework (per v2 §2.4, Python-based) bound strictly to `127.0.0.1` (TDD §20/§28 — a startup assertion test enforces this, not just a config default).
- Implement `AuthTokenManager`: token generated fresh on every Core start, written to the configured path, rotated on restart (TDD §29).
- Implement auth middleware rejecting any request missing/mismatching the token with a proper `AuthenticationException` → `ErrorResponse` (TDD §17).
- Implement the `ErrorResponse` envelope formatter, wired to the Sprint 1 exception hierarchy.
- Implement `/v1/health`.

**Folder Changes:** `core/api/v1/routes_health.*`, `core/api/middleware/auth.*`.

**New Interfaces:** API middleware contract (auth); `ErrorResponse` formatter contract.

**New Classes:** `AuthTokenManager`, `ErrorResponseFormatter`, `HealthController`.

**API Endpoints:** `GET /v1/health` (auth-required).

**Unit Tests:** Token generation/rotation correctness; `ErrorResponse` shape validated against TDD §17.1 schema; middleware rejects missing/bad tokens with the correct `error_code`.

**Integration Tests:** Start Core; call `/v1/health` with a valid token (200, correct JSON shape, `correlation_id` present); call without a token (401); call with a stale token from a previous Core run (401, proving rotation works).

**Acceptance Criteria:** Core is reachable over real HTTP; unauthenticated calls are always rejected; a startup test confirms Core never binds to `0.0.0.0`.

**Risks:** Misconfiguration accidentally exposing the bind address beyond localhost — mitigated by the startup assertion test being part of CI, not just a manual check.

**Deliverables:** Live, authenticated HTTP endpoint.

**Demo Scenario:** `curl` `/v1/health` with and without a token, showing 200 vs. 401; restart Core and show the old token now rejected.

---

## Sprint 3 — CorelDRAW Adapter

**Sprint Goal:** A minimal VBA Adapter running inside CorelDRAW X7 reads the local auth token, calls Core's `/v1/health`, and displays the live result — proving the VBA↔HTTP↔Core round trip, the single riskiest unknown flagged since v2 §11.

**Functional Requirements:** Adapter can authenticate against and confirm connectivity to a running Core process from inside CorelDRAW.

**Technical Tasks:**
- Scaffold the `.gms` VBA project per TDD §40 deployment shape.
- Implement `clsCoreClient` (thin HTTP wrapper only — no logic, per v2 §4's asymmetry rule) using `WinHTTP`/`MSXML2.XMLHTTP`.
- Implement token file reading (shared local path, same convention as Sprint 2's `AuthTokenManager` output).
- Implement a one-button `frmMainToolbar` ("Check Core Connection") that calls `clsCoreClient.GetHealth()` and shows the result.

**Folder Changes:** `adapters/coreldraw/src/App/clsAppController.cls`, `clsCoreClient.cls`, `adapters/coreldraw/src/UI/frmMainToolbar.frm`.

**New Interfaces:** None beyond the already-specified `clsCoreClient` contract (TDD §4, v2 §4).

**New Classes:** `clsCoreClient`, `clsAuthTokenReader`, `frmMainToolbar`.

**API Endpoints:** None new (consumes Sprint 2's `/v1/health` only).

**Unit Tests:** VBA has no native unit-test framework; mitigated with a scripted test harness — a debug macro that asserts expected HTTP status/body shape against a running Core instance, run as part of manual/CI-adjacent verification (documented limitation, not silently ignored).

**Integration Tests:** Automated: a standalone script (outside CorelDRAW) exercises the same HTTP call pattern the Adapter uses, to validate the client logic independent of CorelDRAW's UI thread. Manual: open CorelDRAW, load the macro, click the button, confirm the live status message.

**Acceptance Criteria:** Clicking "Check Core Connection" inside actual CorelDRAW X7 shows a real, live status from a running Core process, authenticated correctly.

**Risks:** This *is* the flagged Phase-2 spike from TDD/v2 risk logs — VBA's HTTP client behavior is the least-proven part of the whole system. If this sprint reveals HTTP-as-IPC is unworkable, the TDD's documented fallback (CLI/file-based IPC, TDD §11 risk table) becomes the next sprint's actual task before proceeding — flagged now so it isn't a surprise.

**Deliverables:** Working `.gms` macro with a functioning toolbar button, demoable inside real CorelDRAW X7.

**Demo Scenario:** Open CorelDRAW with the macro loaded, click the button, see "Core connected, version X.Y.Z."

---

## Sprint 4 — Neutral Geometry Format

**Sprint Goal:** A real artwork file can be imported into CorelDRAW, serialized to the Neutral Geometry Format, sent to Core and echoed back, and re-rendered with no visible distortion — proving the second highest-risk seam in the system (TDD §5.4).

**Functional Requirements:** TDD §5 format definition and §5.4 round-trip contract.

**Technical Tasks:**
- Implement Core-side schema validation for Neutral Geometry (`core/schemas/neutral_geometry.schema.json` + a validator).
- Implement Adapter-side `clsGeometrySerializer`: `ShapeToNeutral()` and `NeutralToShape()`, covering lines, Bézier curves, open/closed subpaths, multi-object layers.
- Build the round-trip epsilon test harness (default 0.001mm, per TDD §5.4).

**Folder Changes:** `core/geometry/format_validator.*`, `core/schemas/neutral_geometry.schema.json`, `adapters/coreldraw/src/CadIO/clsGeometrySerializer.cls`.

**New Interfaces:** `IGeometryValidator` (Core); the Adapter-side serializer contract already specified in TDD §5.4.

**New Classes:** `NeutralGeometryValidator`, `clsGeometrySerializer`.

**API Endpoints:** `POST /v1/geometry/validate-format`, `POST /v1/geometry/round-trip-check` (diagnostic, per TDD §4.2).

**Unit Tests:** Core validator against a fixture library (valid and deliberately invalid payloads); Adapter round-trip tests against a fixture shape set (simple polygon, compound path, nested subpaths, Bézier-heavy signature curve).

**Integration Tests:** Import a real test artwork file into CorelDRAW → serialize → send to Core → receive the echo → re-render → diff node count/bounding box/closedness against tolerance.

**Acceptance Criteria:** Round-trip epsilon ≤0.001mm across the full fixture set; Core rejects malformed payloads with a `GeometryFormatException`/400, never a silent corruption.

**Risks:** Bézier control-point fidelity loss on complex curves is the single most-repeated risk across every prior document — budget extra time here specifically, and don't let this sprint be declared "done" on simple shapes alone.

**Deliverables:** A working, tested round-trip pipeline demoable on a real sample file.

**Demo Scenario:** Import a real logo, click "send to Core and back," overlay before/after to visually confirm no distortion.

---

## Sprint 5 — Geometry Engine

**Sprint Goal:** Core can compute a parametric offset variant and a connectivity graph (bridge/island detection) on Neutral Geometry — the primitives every later engine depends on.

**Functional Requirements:** v3 §11's generic offset operation; connectivity graph for island/bridge analysis.

**Technical Tasks:**
- Implement `CurveUtils` (node reduction primitives, curvature analysis — used later, not exercised fully until Sprint 10).
- Implement `ShapeGraph` (connectivity graph construction, island detection, bridge-width measurement between connected regions).
- Implement `OffsetEngine.generate_offset_variant(geometry, distance, direction)`.
- Add a diagnostic endpoint for manual verification during development.

**Folder Changes:** `core/engines/geometry/curve_utils.*`, `shape_graph.*`, `offset_engine.*`.

**New Interfaces:** `IGeometryEngine` (offset + connectivity operations).

**New Classes:** `CurveUtils`, `ShapeGraph`, `OffsetEngine`.

**API Endpoints:** `POST /v1/geometry/offset` (diagnostic/development use; will also be called internally by later engines, not only externally).

**Unit Tests:** Offset correctness against shapes with a known analytic answer (e.g., a circle offset by a known distance yields the expected radius within tolerance); `ShapeGraph` correctly identifies islands and measures bridge widths on fixtures with deliberately disconnected regions.

**Integration Tests:** Generate an offset shape, round-trip it through the Adapter (Sprint 4's pipeline) to confirm it re-imports into CorelDRAW correctly as real geometry, not just valid JSON.

**Acceptance Criteria:** Offset operations are geometrically correct within tolerance on every fixture shape; island detection correctly flags every known-disconnected fixture and correctly passes every known-connected one (no false positives).

**Risks:** Performance on very large/complex curves (30k+ nodes) — benchmark against TDD §21 targets now, early, rather than discovering a bottleneck once several engines depend on this one.

**Deliverables:** A tested Geometry Engine module plus a diagnostic endpoint.

**Demo Scenario:** Submit a shape, request a positive and negative offset, show both rendered via the Adapter's basic preview.

---

## Sprint 6 — Validation Engine

**Sprint Goal:** Core runs the full standard geometry defect checklist (FR-6) and produces a structured, deterministic `ValidationReport` — with thresholds supplied as explicit caller parameters (no hardcoding), so Sprint 7's Rule Engine becomes the real caller without any rework.

**Functional Requirements:** FR-6 (v3 §1.2).

**Technical Tasks:**
- Implement each check as an independent function: open curves, duplicate nodes, duplicate objects, self-intersections, min gap, min bridge (using Sprint 5's `ShapeGraph`), min wall thickness, floating islands (also via `ShapeGraph`), tiny holes, node density, sharp angles, disconnected objects.
- Implement the `ValidationReport` assembler (per-check pass/fail + location + measured value + threshold, per v3 §6.2).
- All checks accept thresholds as parameters — this sprint's caller (a temporary test harness) supplies fixed reference values explicitly labeled as "test harness defaults," never embedded inside a check's logic.

**Folder Changes:** `core/engines/validation/checks/*`, `core/engines/validation/report_assembler.*`.

**New Interfaces:** `IValidationCheck` (per check type); `IValidationEngine.run_standard_checks()`.

**New Classes:** One class per check (11 total, per v3 §6.2's list), plus `ValidationReportAssembler`.

**API Endpoints:** `POST /v1/validation/validate`.

**Unit Tests:** One passing and one failing fixture per check type, using synthetic minimal geometries designed to isolate each check.

**Integration Tests:** Full checklist run against the curated test document library (government seal, church logo, signature, deliberately corrupted file — v1 §12 precedent) confirming the expected pass/fail pattern per document.

**Acceptance Criteria:** `/v1/validation/validate` returns a correct, complete `ValidationReport` for every fixture; a determinism test (same input run twice) produces byte-identical reports.

**Risks:** None engine-specific; the main risk is a reviewer mistaking the test-harness threshold parameters for hardcoded values — flagged explicitly in code review checklist for this sprint.

**Deliverables:** Working Validation Engine plus report schema plus endpoint.

**Demo Scenario:** Submit each curated test document; show the resulting `ValidationReport`, including a real flagged thin bridge in the signature fixture.

---

## Sprint 7 — Rule Engine

**Sprint Goal:** Core resolves manufacturing rule thresholds through the product→material→machine→default order (v3 §12.3) and becomes the real supplier of thresholds to Sprint 6's Validation Engine — replacing the test-harness parameter, not rewriting the engine.

**Functional Requirements:** FR-7 (versioning groundwork, fully realized in Sprint 8); TDD §9.

**Technical Tasks:**
- Implement `RuleCategoryLoader` reading initial single-version YAML rule files (`bridge_width.yaml`, `gap.yaml`, `wall.yaml`) with defaults only — no material/product overrides yet, since only synthetic test data exists until Sprint 12's real plugin.
- Implement `RuleResolver`: the four-tier resolution algorithm plus `resolution_trace` generation (TDD §9), satisfying the Explainability NFR (v2 §1.3).
- Wire Sprint 6's Validation Engine to call the Rule Engine for real thresholds in the integration path (unit tests continue exercising Validation Engine in isolation with fixture parameters, per TDD §37's isolation principle).

**Folder Changes:** `core/engines/rule_engine/rule_loader.*`, `resolver.*`, initial `core/knowledge_base/rules/*.yaml`.

**New Interfaces:** `IRuleEngine.resolve(product_type, material, machine) → ResolvedRuleSet`.

**New Classes:** `RuleCategoryLoader`, `RuleResolver`.

**API Endpoints:** `GET /v1/rules/resolved`.

**Unit Tests:** Resolution order correctness — each override tier tested independently and in combination (e.g., a product override correctly beats a material override).

**Integration Tests:** Validation Engine driven end-to-end by real resolved rules against the curated test documents; confirm that tightening a threshold (e.g., `bridge_min`) flips a previously-passing fixture to failing, proving the wiring is real, not cosmetic.

**Acceptance Criteria:** `/v1/rules/resolved` returns correct values and a correct `resolution_trace` across a range of product/material/machine combinations; the Validation Engine's threshold parameter is now always Rule-Engine-supplied in the integration path.

**Risks:** Low — this is primarily a wiring sprint.

**Deliverables:** Working Rule Engine, fully integrated with Validation.

**Demo Scenario:** Resolve rules for two different materials, show differing `bridge_min` values with their trace; show validation flipping pass/fail accordingly.

---

## Sprint 8 — Knowledge Base

**Sprint Goal:** Rule categories become versioned, append-only, checksummed, and editable only by an authorized role — the full reproducibility and tamper-evidence guarantee from TDD §17.5/§28.

**Functional Requirements:** FR-7 fully realized.

**Technical Tasks:**
- Implement version history storage (append-only; no UPDATE path exists for a historical version row, only INSERT of new versions).
- Implement checksumming and tamper detection on read.
- Implement a minimal, narrowly-scoped authorization check (`admin`-only) on the single write endpoint this sprint introduces — explicitly *not* building the full Operator/role system yet (that's Enterprise Services, flagged as unscheduled in the Gaps section below); this sprint's check is a small, honest stopgap sized to exactly what's needed now.

**Folder Changes:** `core/engines/knowledge/version_store.*`, `checksum.*`.

**New Interfaces:** `IKnowledgeEngine.get_version_history(category)`, `.propose_new_version(category, values)`.

**New Classes:** `RuleVersionStore`, `ChecksumValidator`.

**API Endpoints:** `GET /v1/rules/{category}/history`, `POST /v1/rules/{category}/versions` (admin-only).

**Unit Tests:** Append-only enforcement (an attempted mutation of a historical version fails); checksum validation detects a deliberately corrupted stored version.

**Integration Tests:** An admin proposes a new rule version; new resolutions use it; a synthetic old-Job-like record pinned to the prior version still resolves against that prior version (full Job-pinning arrives properly in Sprint 11, but the version-store side of this guarantee is provable now).

**Acceptance Criteria:** Version history is queryable and immutable; only the `admin` role can write; tampering is detected and rejected on read.

**Risks:** The narrow role check here is intentionally minimal — flagged so it isn't mistaken for the full authorization model (TDD §30), which arrives with Enterprise Services (unscheduled, see Gaps).

**Deliverables:** A versioned, tamper-evident Knowledge Base.

**Demo Scenario:** Show `bridge_width`'s history across two versions with checksums; demonstrate a rejected read against a deliberately tampered version file.

---

## Sprint 9 — Analysis Engine

**Sprint Goal:** Core computes score, difficulty, risk, success rate, estimated engraving time, and material usage for real artwork — using a documented **fixture plugin** (built specifically for engine testing, per TDD §37) to exercise the `ProductPlugin.analyze()` hook honestly, since the real Emboss Seal plugin doesn't exist until Sprint 12.

**Functional Requirements:** Manufacturing Analysis Engine (v2 FR-24 equivalent); full realization of TDD §2.1's sequence diagram.

**Technical Tasks:**
- Implement the scoring formula (generalizing v1's heuristic advisor logic — node density, min-feature-size, hairline/island counts), difficulty/risk categorization, engraving-time and material-usage estimators.
- Wire the `ProductPlugin.analyze()` hook using a documented fixture plugin — explicitly labeled in the codebase as a test fixture, not a shipped product, per TDD §37's isolation guidance.

**Folder Changes:** `core/engines/analysis/manufacturing_analysis.*`, `formulas.*`; `core/tests/fixtures/fixture_plugin/`.

**New Interfaces:** `IAnalysisEngine.analyze(...)`.

**New Classes:** `ManufacturingAnalysisEngine`, `ScoreCalculator`, `TimeEstimator`, `MaterialUsageEstimator`.

**API Endpoints:** `POST /v1/analysis/analyze`.

**Unit Tests:** Formula correctness on synthetic geometries with hand-computed expected scores; plugin-hook invocation verified via the fixture plugin.

**Integration Tests:** Full TDD §2.1 sequence executed end-to-end against the curated test documents, results compared against manually-estimated expected ranges.

**Acceptance Criteria:** `/v1/analysis/analyze` returns a complete `AnalysisResult`; determinism holds; TDD §21 performance targets (<2s typical, <8s complex) are measured and either met or explicitly flagged as a follow-up if missed.

**Risks:** The scoring formula is a first-draft calibration with no real manufacturing outcome data yet — explicitly labeled "rule-of-thumb v1" in documentation and UI, not presented as final (consistent with TDD §14.2's data-collection-from-day-one plan).

**Deliverables:** Working Analysis Engine, endpoint, and a performance benchmark report.

**Demo Scenario:** Submit the curated test documents; show full `AnalysisResult` output (score, difficulty, risk, time, material usage) with real computed numbers.

---

## Sprint 10 — Repair Engine

**Sprint Goal:** Core (and, for native-op fast-path repairs, the Adapter) can automatically repair a defective geometry within a bounded loop (max 3 attempts, per your approved TDD decision), preserving visual similarity, and correctly falls back to `NEEDS_REVIEW` when it can't.

**Functional Requirements:** Automatic Repair Engine (v2 FR-25 equivalent); TDD §2.2's bounded loop.

**Technical Tasks:**
- Implement Core-side repair actions on Neutral Geometry: close open curves, join nearby endpoints, remove exact duplicates, remove tiny islands (using Sprint 5's `ShapeGraph`), simplify excessive nodes.
- Implement the bounded loop orchestrator (3 attempts default, configurable per Product Definition per TDD §7; exits to `NEEDS_REVIEW` at the limit).
- Implement a similarity scorer (e.g., filled-area overlap or node-count delta against tolerance).
- Implement Adapter-side `clsNativeOps` for the CorelDRAW-native fast-path operations (weld, PowerTRACE-driven simplify) that v3 §2.3 designates as pre-processing convenience, run before geometry crosses the boundary.

**Folder Changes:** `core/engines/repair/repair_actions/*`, `loop_orchestrator.*`, `similarity_scorer.*`; `adapters/coreldraw/src/CadIO/clsNativeOps.cls`.

**New Interfaces:** `IRepairEngine.repair(...)`; `IRepairAction` per action type.

**New Classes:** `CloseCurveRepair`, `JoinEndpointsRepair`, `RemoveDuplicatesRepair`, `RemoveTinyIslandRepair`, `SimplifyNodesRepair`, `RepairLoopOrchestrator`, `SimilarityScorer`, `clsNativeOps`.

**API Endpoints:** `POST /v1/repair/repair`.

**Unit Tests:** Each repair action against a fixture with a known, specific defect, confirming the defect is fixed and similarity stays within tolerance; loop orchestrator tested for correct exit at exactly 3 attempts and correct `NEEDS_REVIEW` fallback.

**Integration Tests:** Full TDD §2.2 repair-loop sequence run against the deliberately-corrupted curated test fixture, with re-validation (via Sprint 6/7) after every attempt.

**Acceptance Criteria:** The loop terminates correctly on pass or on reaching the attempt limit; repaired geometry re-validates clean where genuinely fixable; every action taken is reported with its similarity impact.

**Risks:** Similarity preservation and defect-fixing can genuinely conflict (e.g., closing a large gap may shift the shape more than tolerance allows) — this is a real engineering judgment call, not a bug to "fix away"; the fixture test set is specifically designed to surface this tension so it's visible in review, not hidden.

**Deliverables:** A working bounded repair pipeline, both Core and Adapter sides.

**Demo Scenario:** Submit the corrupted test fixture; show it pass through the repair loop; display before/after with the similarity score and the list of actions taken.

---

## Sprint 11 — Workflow Engine

**Sprint Goal:** Jobs exist as real, persisted entities and move through the default platform Workflow (Order Received → ... → Archive) via a correctly-validated, crash-recoverable state machine.

**Functional Requirements:** FR-4; TDD §8/§31.

**Technical Tasks:**
- Implement `WorkflowDefinitionLoader` with structural validation (every state reachable, no dead-end non-terminal states — TDD §8).
- Implement `WorkflowInstanceManager`: `start()`/`advance()`, transactional per TDD §23 (fully applies or fully fails, never partial).
- Author the default platform `WorkflowDefinition` YAML (v3 §10.2's sequence).
- Introduce the `Job` entity and its first real persistence (this is the first sprint requiring a real database — set up SQLite with a lightweight migration tool now, since every later sprint depends on this schema being managed correctly from the start).

**Folder Changes:** `core/engines/workflow/definition_loader.*`, `instance_manager.*`; `core/data/models.*` (Job, WorkflowInstance tables); migration tooling setup.

**New Interfaces:** `IWorkflowEngine.start(job, definition)`, `.advance(instance, event)`.

**New Classes:** `WorkflowDefinitionLoader`, `WorkflowInstanceManager`, a minimal `JobRepository`.

**API Endpoints:** `POST /v1/jobs` (minimal create), `POST /v1/workflow/start`, `POST /v1/workflow/advance`, `GET /v1/workflow/{instance_id}`.

**Unit Tests:** Structural validation correctly rejects fixture definitions with unreachable states or dead ends; transition guard evaluation; transactional `advance()` behavior (no partial transitions observable, even under simulated failure mid-operation).

**Integration Tests:** Drive a job through the entire default workflow via a sequence of real API calls, confirming persisted history at every step; kill Core mid-transition and confirm correct resumption on restart (TDD §27).

**Acceptance Criteria:** The default workflow loads and validates cleanly; a job can be driven end-to-end through every state via the API; the crash-recovery test passes.

**Risks:** This is the first sprint with real persistence — schema/migration discipline established here is inherited by every subsequent sprint; getting this wrong now compounds, so extra review attention is warranted here specifically.

**Deliverables:** A working Workflow Engine, minimal Job API, and SQLite persistence.

**Demo Scenario:** Create a job, drive it through the full default workflow via API calls, show its state history; kill and restart Core mid-flow to demonstrate recovery live.

---

## Sprint 12 — Emboss Seal Plugin

**Sprint Goal:** The first real product plugin is built and registered, replacing the Sprint 9 fixture plugin in actual use (the fixture plugin remains, permanently, only inside engine unit tests, per TDD §37).

**Functional Requirements:** FR-2/FR-3 (Product Definition load and configure); v3 §8 in full.

**Technical Tasks:**
- Author `products/emboss_seal/product_definition.yaml`: rule categories used, validation rules enabled, repair rules enabled, machine/material compatibility, output formats, layer structure, an initial preset list (full preset value tuning continues in Sprint 13+).
- Implement the `EmbossSealPlugin`'s `validate()`, `analyze()`, and `repair()` hooks with genuine embossing-specific judgment (e.g., is this specific shape topologically suitable for embossing — beyond what the generic Validation Engine already checks).
- Run the plugin through the Conformance Suite (TDD §2.3/§37) for real registration at Core startup.

**Folder Changes:** `products/emboss_seal/product_definition.yaml`, `validation_rules.yaml`, `repair_rules.yaml`, `plugin_code/`.

**New Interfaces:** None new — this sprint implements existing `IProductPlugin`/`ProductDefinition` contracts for the first time with real content.

**New Classes:** `EmbossSealPlugin`.

**API Endpoints:** None new — `GET /v1/products` (already specified, TDD §4.2) now returns real data for the first time.

**Unit Tests:** Conformance suite pass/fail tests against this real definition; plugin-specific hook unit tests using embossing-specific fixtures.

**Integration Tests:** A full end-to-end job (Sprints 9–11's pipeline) run using the real Emboss Seal plugin against the curated test document library, replacing the fixture plugin in these specific tests.

**Acceptance Criteria:** `emboss_seal` registers successfully at Core startup; a full job lifecycle (import → analyze → repair → ... → archive) runs correctly using real embossing rules end-to-end.

**Risks:** This is the first real stress test of every engine contract against genuine product-specific logic — some friction at a contract boundary is expected and should be documented as a finding for retrospective, not silently patched around (Engineering Rule 10).

**Deliverables:** A fully working, registered Emboss Seal plugin.

**Demo Scenario:** Run a real embossing seal artwork sample end-to-end, from import to an archived job record, using only the real plugin — no test fixtures anywhere in the path.

---

## Sprint 13 — Male/Female Generator

**Sprint Goal:** Approved job geometry produces correctly-cleared Male and Female die geometry, with registration marks and an engraving boundary, organized onto the correct named layers.

**Functional Requirements:** v1 FR-13/14/15/16 (folded into this sprint since the roadmap doesn't list them separately) and FR-36 (layer taxonomy).

**Technical Tasks:**
- Implement `generate_outputs()` for Emboss Seal: call Sprint 5's `generate_offset_variant()` twice (positive/negative directions), using clearance from the Rule Engine (Sprint 7) resolved for the active material/machine, and label the two results Male/Female (v3 §11's point that this labeling is plugin-specific, not Core knowledge).
- Implement registration-mark and engraving-boundary generation as further plugin-specific output.
- Implement Adapter-side `clsLayerManager` (`EnsureLayer`/`PlaceOnLayer`) realizing the eight-role layer taxonomy (Original/Repair/Male/Female/Registration/Cut/Engraving/Target-System).

**Folder Changes:** `products/emboss_seal/plugin_code/male_female_generator.*`; `adapters/coreldraw/src/CadIO/clsLayerManager.cls`.

**New Interfaces:** None new — uses the existing `generate_outputs()` contract.

**New Classes:** `MaleFemaleGenerator`, `RegistrationMarkGenerator`, `BoundaryGenerator` (all within `plugin_code/`), `clsLayerManager`.

**API Endpoints:** `POST /v1/jobs/{id}/generate-outputs`.

**Unit Tests:** Offset clearance correctness against resolved rule values; registration mark placement geometry; layer-assignment correctness.

**Integration Tests:** A full job run producing Male, Female, Registration, and Boundary geometry, placed on the correct named layers in a real CorelDRAW document via the Adapter, visually inspected against the expected layout.

**Acceptance Criteria:** Given approved geometry, the system produces correctly-cleared dies with registration marks and boundary, correctly organized into the eight-layer taxonomy.

**Risks:** Clearance/kerf interaction with real material spring-back remains a physical unknown until an actual laser test (flagged consistently since v1) — generated clearance values should be treated as first-draft pending physical validation, not as final tuned constants.

**Deliverables:** A working Male/Female generation pipeline with layer management.

**Demo Scenario:** Run a job through to output generation; show the resulting CorelDRAW document with every layer correctly populated.

---

## Sprint 14 — Preview Generator

**Sprint Goal:** Male, Female, paper-impression, and cross-section previews render correctly for a real job, with a weak-area overlay derived from actual validation data.

**Functional Requirements:** Emboss Preview Simulator (v2 spec).

**Note on a deferred-module conflict:** v2 originally described this as a generic Core "Emboss Preview Simulator" rendering via the Template Engine's `preview_templates`. Since the Template Engine is 🔴 deferred, this sprint implements rendering as **Emboss Seal plugin code** calling `generate_preview()` (exactly as v3 §8.3 intends product-specific behavior to work), with Core providing only a generic, reusable rasterization/rendering *utility* — not a full templating engine. This keeps the sprint buildable now without secretly depending on unbuilt infrastructure.

**Technical Tasks:**
- Implement a generic Core rendering utility (SVG-to-raster or equivalent) usable by any plugin later.
- Implement Emboss Seal's `generate_preview()`: Male/Female renders, a simple paper-impression simulation, a cross-section view (using material thickness and emboss depth from resolved rules), and a weak-area overlay driven by Sprint 6/5's bridge-violation data.
- Implement Adapter-side `frmPreviewSimulator` with four tabs.

**Folder Changes:** `core/engines/rendering/raster_utility.*` (generic); `products/emboss_seal/plugin_code/preview_renderer.*`; `adapters/coreldraw/src/UI/frmPreviewSimulator.frm`.

**New Interfaces:** None new — uses the existing `generate_preview()` contract; adds the internal generic rendering utility interface.

**New Classes:** `RasterUtility` (Core, generic), `EmbossPreviewRenderer`, `WeakAreaOverlayRenderer` (both plugin-specific), `frmPreviewSimulator`.

**API Endpoints:** `POST /v1/preview/generate` (this route group was not explicitly enumerated in TDD §4.2's table — added now, consistent with the existing versioning/error conventions, not a new pattern).

**Unit Tests:** Weak-area overlay correctly highlights known bridge-violation fixtures; cross-section geometry correctness for known thickness/depth inputs.

**Integration Tests:** Full preview generation for a real approved job, all four views inspected against expected output; determinism confirmed (same job renders identically on repeat).

**Acceptance Criteria:** All four views render correctly and consistently for a real Emboss Seal job; the weak-area overlay matches the Validation Engine's actual flagged violations exactly (not an approximation).

**Risks:** The rendering approach itself is unproven (flagged since v2 §8's Phase 8 risk) — a small time-boxed spike at the start of this sprint, before full build-out, is recommended rather than assumed.

**Deliverables:** Working preview generation plus the Adapter's preview panel.

**Demo Scenario:** Show all four preview tabs for a real job; toggle the weak-area overlay live.

---

## Sprint 15 — DXF Export

**Sprint Goal:** A completed job exports to DXF unattended (no blocking dialogs), with correct layer structure and geometry fidelity.

**Functional Requirements:** FR-18/19 (partially — full RDWorks-specific compatibility is Sprint 16).

**Technical Tasks:**
- Implement Adapter-side `clsExport.ExportDXF()`, with the export filter GUID explicitly pinned (v1 §9's known risk — CorelDRAW can otherwise silently fall back to "last used filter" and pop a blocking dialog in unattended runs).
- Wire export into the "Laser Processing" workflow state as its entry action.

**Folder Changes:** `adapters/coreldraw/src/CadIO/clsExport.cls` (DXF handling this sprint; other formats are a documented gap, see Gaps section).

**New Interfaces:** `IExportHandler` (per format, designed for extension by later formats without modification — satisfies Engineering Rule 9's backward-compatibility principle from the start).

**New Classes:** `DxfExportHandler`.

**API Endpoints:** `POST /v1/jobs/{id}/export` (with a `format` parameter; only `dxf` supported this sprint).

**Unit Tests:** Filter GUID pinning regression test (fails if a future change accidentally reverts to filter auto-selection); output file naming convention correctness.

**Integration Tests:** Export a real completed job's full layer set to DXF; re-open/re-import and confirm node count and layer names are preserved.

**Acceptance Criteria:** DXF export completes fully unattended, with no dialog interaction required, and correct fidelity.

**Risks:** DXF's polyline-based curve representation can lose fidelity on complex Bézier curves relative to CorelDRAW's native model — test this explicitly against the signature-style fixture, the worst case.

**Deliverables:** Working, unattended DXF export.

**Demo Scenario:** Run a job to completion, export to DXF, open the result in a neutral DXF viewer to confirm correctness.

---

## Sprint 16 — RDWorks Compatibility

**Sprint Goal:** Exported DXF files import into RDWorks with zero manual cleanup and correct laser-parameter-by-color assignment — the concrete meaning of "RDWorks-ready" (v1 §1.5).

**Functional Requirements:** FR-19, generalized per v3 §1.3's "Target System Compatibility."

**Technical Tasks:**
- Implement `RDWorksLayoutBuilder`: assigns colors per layer role according to a configurable mapping declared on the Machine Profile's `target_systems` entry.
- Reuse Sprint 6's closed-path validation check as part of export-integrity verification (not a duplicate implementation — the same check, run again, per the principle established in v3 §6.2/§14.4).

**Folder Changes:** `core/export/rdworks_layout_builder.*` (new `core/export/` grouping for target-system-specific concerns, distinct from the generic `core/engines/`).

**New Interfaces:** `ITargetSystemLayoutBuilder`.

**New Classes:** `RDWorksLayoutBuilder`.

**API Endpoints:** Extends Sprint 15's `POST /v1/jobs/{id}/export` with a `target_system` parameter (backward-compatible addition, per Engineering Rule 9 — not a new endpoint).

**Unit Tests:** Color-mapping correctness per layer role; closed-path validation correctly catches an open path intended for cut/engrave.

**Integration Tests:** A real, manual RDWorks import test using actual RDWorks software — flagged explicitly as a **manual acceptance step**, since RDWorks has no automation surface (v1 §1.5) and this cannot be part of automated CI.

**Acceptance Criteria:** The exported DXF imports into real RDWorks with zero manual cleanup and correct color-to-laser-parameter assignment.

**Risks:** Because RDWorks can't be automated, every regression check against it requires a human with RDWorks access — this is a standing process cost for this feature area, not a one-time sprint cost, and should be budgeted into future regression cycles accordingly.

**Deliverables:** A working, verified RDWorks-ready export.

**Demo Scenario:** Export a job, import it into actual RDWorks live, show correct color/layer assignment.

---

## Sprint 17 — Quality Inspection

**Sprint Goal:** Before export, Core re-runs the full validation checklist on final output geometry plus machine/material compatibility and export-integrity checks, producing a real PASS/WARNING/FAIL that correctly gates the workflow.

**Functional Requirements:** FR-8; TDD §2.4's sequence fully realized.

**Technical Tasks:**
- Implement machine and material compatibility checkers.
- Wire the Quality Inspection module into the Workflow Engine's "Quality Inspection" state as an entry action, using **the same Validation Engine code path** as pre-repair validation (v2 §6.2/§14.4's explicit non-duplication principle) — this sprint includes a specific test asserting the same check implementation is invoked in both places, not two parallel implementations.

**Folder Changes:** `core/enterprise/quality_inspection/*` (per the v3 folder structure — this had been reserved but unbuilt until now).

**New Interfaces:** `IQualityInspectionEngine.inspect(job) → PASS|WARNING|FAIL`.

**New Classes:** `QualityInspectionEngine`, `MachineCompatibilityChecker`, `MaterialCompatibilityChecker`.

**API Endpoints:** `POST /v1/jobs/{id}/quality-inspection`.

**Unit Tests:** Compatibility logic against fixture machine/material pairs with known expected outcomes; a specific test confirming the same validation-check code path is reused pre- and post-repair (not reimplemented).

**Integration Tests:** Full workflow run through the Quality Inspection state using deliberately-crafted good/marginal/bad fixture jobs, confirming correct PASS/WARNING/FAIL outcomes and correct downstream workflow behavior (FAIL blocks progression, WARNING flags but allows, PASS proceeds).

**Acceptance Criteria:** Quality Inspection correctly gates the workflow for all three outcome categories.

**Risks:** Low — this sprint is primarily integration of already-built pieces.

**Deliverables:** A working Quality Inspection gate.

**Demo Scenario:** Run three jobs (good, marginal, bad) through to Quality Inspection; show the differing outcomes and resulting workflow behavior.

---

## Sprint 18 — Reporting

**Sprint Goal:** Every completed job produces a correctly-populated PDF production report.

**Functional Requirements:** Production Report Generator (v2 spec).

**Note on the same deferred-module conflict as Sprint 14:** report templates were originally scoped through the deferred Template Engine. This sprint instead implements report content assembly as **Emboss Seal plugin code**, with Core providing a generic, reusable PDF-rendering utility — the same resolution pattern as Sprint 14, kept consistent rather than inventing a new workaround.

**Technical Tasks:**
- Implement a generic Core PDF rendering utility.
- Implement Emboss Seal-specific report content assembly (summary, manufacturing parameters, pass/fail, warnings/recommendations sections, per TDD §14 schema).
- Wire report generation into the workflow as an action at the Archive state (or Quality Inspection completion — whichever the default workflow's entry actions specify).

**Folder Changes:** `core/engines/reporting/pdf_renderer.*` (generic); `products/emboss_seal/plugin_code/report_builder.*`.

**New Interfaces:** `IReportingEngine.generate(job, template_ref)`.

**New Classes:** `PdfRenderer` (generic), `EmbossSealReportBuilder` (plugin-specific).

**API Endpoints:** `POST /v1/reports/generate`, `GET /v1/reports/{id}`.

**Unit Tests:** PDF structural tests (required sections present); report content correctness against known job data.

**Integration Tests:** A full job run producing a final PDF, validated for all required sections.

**Acceptance Criteria:** Every completed job has a retrievable, correctly-populated PDF report.

**Risks:** Low — PDF generation is a well-trodden problem; the only real risk is section-content correctness, covered by the integration test.

**Deliverables:** Working report generation.

**Demo Scenario:** Complete a job, generate its report, open the resulting PDF.

---

## Sprint 19 — Batch Processing

**Sprint Goal:** A folder of artwork files processes sequentially and unattended, with per-job pass/fail/needs-review status and a correct consolidated report.

**Functional Requirements:** FR-31 (v2 spec); TDD §2's batch orchestration.

**Technical Tasks:**
- Implement `BatchOrchestrator` (Core-side): enumerate files, create Job records, sequence processing.
- Implement Adapter-side headless-run mode: process a single job through the full pipeline (Sprints 4–18) without manual UI interaction per file.
- Implement consolidated batch reporting.

**Folder Changes:** `core/engines/batch/batch_orchestrator.*`; headless-mode additions in `adapters/coreldraw/src/App/`.

**New Interfaces:** `IBatchOrchestrator.start_batch(folder, preset, machine)`, `.get_batch_status(batch_id)`.

**New Classes:** `BatchOrchestrator`, `HeadlessJobRunner`.

**API Endpoints:** `POST /v1/batch/start`, `GET /v1/batch/{id}/status`, `GET /v1/batch/{id}/report`.

**Unit Tests:** Correct file enumeration and Job-record creation; correct sequencing; a single file's failure does not halt the batch (isolation, mirroring the plugin-registration-failure-isolation principle from TDD §2.3).

**Integration Tests:** A real batch run over the curated test document folder plus real Emboss Seal samples, confirming correct per-job status and consolidated report accuracy.

**Acceptance Criteria:** A folder of N files processes to completion (or documented per-file failure) unattended, with a correct consolidated report.

**Risks:** Throughput is bounded by CorelDRAW automation speed per file, not by Core (flagged since v2 §16) — measure real per-file timing now against TDD §21 targets rather than assuming.

**Deliverables:** Working batch processing.

**Demo Scenario:** Point the batch processor at a real folder of 5–10 files, run unattended, show the consolidated report.

---

## Sprint 20 — Rubber Stamp Plugin

**Sprint Goal:** The second real product plugin is built — the "rule of three" validation point Architecture v3 §0.2 has flagged since the very first design pass — genuinely stress-testing every Core contract against a product that isn't Emboss Seal.

**Functional Requirements:** Full Product Definition/Plugin contract exercised a second time, independently.

**Technical Tasks:**
- Author `products/rubber_stamp/product_definition.yaml`: likely different rule categories (e.g., ink-channel-width per v3 §12.2's own example), possibly a different layer structure (may not need the Male/Female offset concept at all), different presets.
- Implement `RubberStampPlugin`'s hooks.
- Run the full pipeline (Sprints 9–19) against it: analysis, repair, workflow, quality inspection, reporting, batch.
- Run the cross-plugin regression suite (TDD §39) for the first time with two genuinely real plugins — this is the concrete mechanism that catches "fixed for Emboss Seal, silently broke Rubber Stamp."

**Folder Changes:** `products/rubber_stamp/*`.

**New Interfaces:** None *expected* — proving that none are needed is this sprint's actual job. If a gap is found, it's documented as a formal finding for a reviewed, deliberate refactor (Engineering Rule 10), not patched invisibly.

**New Classes:** `RubberStampPlugin`.

**API Endpoints:** None new — `GET /v1/products` now correctly lists two real, independently-functioning plugins.

**Unit Tests:** Conformance suite plus plugin-specific hook tests.

**Integration Tests:** A full end-to-end job and batch run using Rubber Stamp; the cross-plugin regression suite run for both plugins together.

**Acceptance Criteria:** Rubber Stamp registers and runs a complete job lifecycle correctly; the cross-plugin regression suite passes for both plugins; any Core contract gap discovered is written up as a formal finding.

**Risks:** This sprint is explicitly the validation checkpoint every prior document has been flagging — a real finding here is a *success* of the process (it means the rule-of-three caution was warranted), not a failure of Sprints 1–19. Budget real time for a genuine, reviewed refactor if warranted rather than a quick patch.

**Deliverables:** A working Rubber Stamp plugin plus a written retrospective of any Core contract findings.

**Demo Scenario:** Run a real rubber stamp job and a real emboss seal job side by side end-to-end, on the same running Core, demonstrating genuine product-independence.

---

## Critical Path

```
Sprint 0 → Sprint 1 → Sprint 2 → Sprint 3 ─────────────────────┐  (Adapter HTTP viability — hard gate)
                                    │                            │
                                    ▼                            ▼
                              Sprint 4 (Geometry round-trip — hard gate, second riskiest seam)
                                    │
                                    ▼
                              Sprint 5 (Geometry Engine primitives)
                                    │
                        ┌───────────┴───────────┐
                        ▼                        ▼
                  Sprint 6 (Validation)    [could start in parallel: Adapter UI shells,
                        │                   clsLayerManager scaffolding — non-blocking work]
                        ▼
                  Sprint 7 (Rules) → Sprint 8 (Knowledge Base versioning — not on critical path,
                        │                       can trail behind Sprint 9+ without blocking them)
                        ▼
                  Sprint 9 (Analysis)
                        │
                        ▼
                  Sprint 10 (Repair)
                        │
                        ▼
                  Sprint 11 (Workflow + first real persistence)
                        │
                        ▼
                  Sprint 12 (Emboss Seal Plugin — first rule-of-three data point)
                        │
              ┌─────────┼─────────┐
              ▼         ▼         ▼
        Sprint 13   Sprint 14  Sprint 15  (Male/Female, Preview, Export — largely parallelizable
              │         │         │        once Sprint 12 lands, if team size allows)
              └─────────┴─────────┘
                        ▼
                  Sprint 16 (RDWorks — depends on 15)
                        ▼
                  Sprint 17 (Quality Inspection — depends on 6/7/16)
                        ▼
                  Sprint 18 (Reporting — depends on 17's data)
                        ▼
                  Sprint 19 (Batch — depends on the full pipeline, 4 through 18)
                        ▼
                  Sprint 20 (Rubber Stamp — the validation checkpoint; depends on everything)
```

**True hard gates (cannot parallelize around):** Sprint 3 (Adapter HTTP viability) and Sprint 4 (geometry round-trip fidelity) are the two risks every prior document has flagged repeatedly. If either reveals a fundamental problem, the fallback plans already documented (CLI/file IPC for Sprint 3; extended round-trip tolerance work for Sprint 4) become real critical-path work, not optional polish — plan schedule buffer here specifically, not spread evenly across all 20 sprints.

**Real parallelization opportunity:** Sprints 13–15, once Sprint 12 lands, don't depend on each other and can run concurrently with a two-track team (one Core-focused, one Adapter-focused) — this is the best opportunity to compress the schedule if more than one engineer is available.

**Sprint 8 is explicitly off the critical path** — Knowledge Base versioning matters for reproducibility and audit but nothing downstream is blocked waiting on it; it can trail behind Sprint 9 by a sprint or two if schedule pressure requires it, without stalling the pipeline.

---

## Effort Estimates

Estimates assume a small team (roughly 1–2 engineers: one Core/Python-focused, one Adapter/VBA-focused) and are given in **engineer-weeks**, not calendar weeks — a two-person team roughly halves calendar time on parallelizable sprints.

| Sprint | Engineer-Weeks | Confidence | Note |
|---|---|---|---|
| 0. Dev Environment | 1 | High | Low complexity, well-understood |
| 1. Core Skeleton | 1 | High | |
| 2. Core API | 1 | High | |
| 3. CorelDRAW Adapter | 2 | **Low** | Highest-risk spike; could run 1–4 weeks depending on what's found |
| 4. Neutral Geometry Format | 2 | **Low** | Second-highest risk; Bézier fidelity work is unpredictable |
| 5. Geometry Engine | 1.5 | Medium | |
| 6. Validation Engine | 2 | Medium | 11 checks is real breadth, each individually simple |
| 7. Rule Engine | 1 | High | Mostly wiring |
| 8. Knowledge Base | 1 | High | Off critical path |
| 9. Analysis Engine | 1.5 | Medium | Formula calibration is inherently soft |
| 10. Repair Engine | 2 | Medium | Similarity-vs-repair tension adds real judgment time |
| 11. Workflow Engine | 2 | Medium | First real persistence layer — schema care takes time |
| 12. Emboss Seal Plugin | 1.5 | Medium | First real contract stress test — expect some friction |
| 13. Male/Female Generator | 1 | High | |
| 14. Preview Generator | 1.5 | **Low** | Rendering approach unproven |
| 15. DXF Export | 1 | Medium | CorelDRAW export quirks are a known but bounded risk |
| 16. RDWorks Compatibility | 1 | Medium | Manual verification loop adds calendar (not engineer) time |
| 17. Quality Inspection | 0.5 | High | Mostly integration of existing pieces |
| 18. Reporting | 1 | High | |
| 19. Batch Processing | 1 | Medium | |
| 20. Rubber Stamp Plugin | 2 | **Low** | The validation checkpoint — genuinely unpredictable by design |
| **Total** | **~27.5 engineer-weeks** | | |

**Reading this honestly:** ~27.5 engineer-weeks is roughly 6–7 months for a single engineer working alone, or meaningfully compressed (4–5 months) with two engineers exploiting the parallelization window in Sprints 13–15 and letting Sprint 8 trail. The three sprints marked **Low confidence** (3, 4, 20) are exactly the three the entire design process has been flagging since v1/v2 — I'd recommend treating their estimates as floors, not ceilings, and building schedule slack around them specifically rather than distributing risk margin evenly across all 20 sprints.

---

## Gaps in the Given 20-Sprint List — Flagging, Not Silently Filling

TDD v1 specified Queue Management, Enterprise Services (operators/customers/licensing), and Notifications as 🟡 buildable-but-not-speculative. None appear in your 20-sprint list. I've built Sprints 0–20 exactly as you specified rather than inserting extra numbered sprints uninvited, but want this gap on record before Sprint 0 begins:

- **Sprint 21 (proposed): Queue Management** — Queued/Running/Paused/Completed/Failed/Cancelled tracking, independent of Workflow state (TDD §15).
- **Sprint 22 (proposed): Enterprise Services** — real Operator roles/authorization (TDD §30, only stubbed narrowly in Sprint 8), Customer records, licensing.
- **Sprint 23 (proposed): Notifications** — event-driven in-app notifications (TDD §16/§32), the first real consumer of the Event Bus beyond logging.

None of these block Sprints 0–20 as written — the pipeline works end-to-end without them, which is exactly why they weren't on your critical path. Flagging now so they're a conscious decision to schedule later, not an oversight discovered mid-Sprint-19.

---

## Summary

Sprints 0–20 as specified deliver a working, tested, product-independent manufacturing pipeline with two real, contract-validated plugins by the end. The critical path runs essentially linearly through Sprint 12, with a genuine parallelization window in Sprints 13–15. Sprints 3, 4, and 20 carry the real schedule risk and should be budgeted accordingly. Sprints 8, 21, 22, and 23 are off the pipeline's critical path and can be sequenced flexibly around team capacity.

No code has been written. Once you approve this plan, Sprint 0 is ready to begin.
