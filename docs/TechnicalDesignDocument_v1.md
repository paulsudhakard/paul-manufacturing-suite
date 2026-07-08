# PMS — Technical Design Document (TDD v1.0)
### Bridging Architecture v3 to Implementation

**Status:** Pre-implementation. Architecture v3 is frozen and treated as authoritative input here — nothing in this document contradicts it; where a design question in this doc would require an architectural change, it's flagged explicitly rather than silently resolved (§0.1).
**Scope note:** No implementation code, no Python, no VBA. All interfaces below are contracts — described by responsibility, inputs, outputs, and constraints — not implementation classes.

---

## 0. How to Read This Document

### 0.1 Relationship to Architecture v3
Architecture v3 established *what exists* (engines, their responsibilities, the Product Definition contract) and *why* (confidence levels, the rule-of-three caution). This TDD establishes *the exact shape of the data and calls* between those things, so that implementation in Phase 1 doesn't require re-deriving design decisions mid-code. Where v3 marked something 🔴 Speculative (Template Engine, Asset Management, Extension SDK Tier 3), this TDD gives it a schema for documentation completeness but does not treat that schema as committed — consistent with your instruction not to implement those until validated.

### 0.2 Assumptions carried in from v2/v3 (stated once, not re-argued)
- Core is a local process (Option A), implementation language Python, exposing a REST/JSON API to Adapters.
- Emboss Seal is Plugin #1 (existing design); Rubber Stamp is Plugin #2 (planned, not yet built).
- CorelDRAW/VBA is the only Adapter that exists; the Adapter contract must not assume it's the only one that ever will.

---

## 1. Module Dependency Diagram

```
                        ┌───────────────────┐
                        │   Plugin Engine     │◄──── products/*/product_definition.yaml
                        └─────────┬─────────┘
                                  │ provides ProductDefinition + ProductPlugin
        ┌─────────────────────────┼─────────────────────────┐
        ▼                         ▼                         ▼
┌───────────────┐       ┌──────────────────┐      ┌──────────────────┐
│ Rule Engine     │◄─────┤ Knowledge Engine   │      │ Workflow Engine    │
│ (resolves rules)│      │ (stores versions)  │      │ (state machine)    │
└───────┬───────┘       └──────────────────┘      └─────────┬────────┘
        │ resolved rules                                      │ drives job state
        ▼                                                      ▼
┌───────────────┐   ┌──────────────────┐   ┌───────────────┐  ┌────────────────┐
│ Validation Eng. │──►│ Analysis Engine   │──►│ Repair Engine   │  │ Queue Engine     │
│ (geometry checks)│  │ (score/risk/time) │  │ (auto-fix)      │  │ (job scheduling) │
└───────┬───────┘   └──────────┬───────┘   └───────┬───────┘  └────────────────┘
        │ uses                  │ uses                │ uses
        ▼                       ▼                     ▼
┌───────────────┐      ┌────────────────┐    ┌───────────────┐
│ Geometry Engine │◄─────┤ Machine Engine  │    │ Material Engine │
│ (curve/offset/  │      │ (profiles,      │    │ (profiles,      │
│  connectivity)  │      │  power/speed)   │    │  thickness etc.)│
└───────────────┘      └────────────────┘    └───────────────┘

Cross-cutting (depended on by nearly everything above, depend on nothing above):
  Logging Engine · Error/Exception Model · Configuration · Event Bus · Security/Auth

Downstream of the pipeline (consume results, don't feed back into it):
  Reporting Engine · Notification Engine · Template Engine 🟡 · Asset Mgmt Engine 🟡
```

**Dependency rule enforced:** arrows only point "inward/downward" toward Geometry/Machine/Material or "cross-cutting" — no engine in the upper pipeline may be depended on by a lower one (e.g., Geometry Engine must never import or call Analysis Engine). This is checked by a static import-graph test in CI (§37).

---

## 2. Sequence Diagrams

### 2.1 Job Creation → Analysis (the core request path)

```
Adapter          Core API        Plugin Engine   Rule Engine   Validation Engine   Analysis Engine
  │  POST /jobs      │                  │              │               │                  │
  │─────────────────►│                  │              │               │                  │
  │                  │ load(product_type)               │               │                  │
  │                  │─────────────────►│              │               │                  │
  │                  │◄─────────────────│ ProductDefinition + ProductPlugin                 │
  │                  │ resolve(product, material, machine)             │                  │
  │                  │──────────────────────────────────►│               │                  │
  │                  │◄──────────────────────────────────│ ResolvedRuleSet                  │
  │                  │ run_standard_checks(geometry)                    │                  │
  │                  │───────────────────────────────────────────────►│                  │
  │                  │◄───────────────────────────────────────────────│ ValidationReport   │
  │                  │ analyze(geometry, rules, report, machine, material)                  │
  │                  │──────────────────────────────────────────────────────────────────►│
  │                  │◄──────────────────────────────────────────────────────────────────│
  │                  │        AnalysisResult (score, difficulty, risk, time, usage)         │
  │◄─────────────────│ 200 OK { job_id, analysis_result }                                  │
```

### 2.2 Automatic Repair Loop (bounded retry)

```
Adapter        Core API      Analysis Engine   Repair Engine   ProductPlugin.repair()
  │ score < threshold?                │               │                  │
  │              │──────► [attempt = 1..N, N configurable, default 3]     │
  │              │        │                │               │                │
  │              │        │ repair(geometry, rules, tolerance)             │
  │              │        │───────────────►│                │
  │              │        │                │─────hook──────►│
  │              │        │                │◄───────────────│ product-specific repair
  │              │        │◄───────────────│ RepairResult (similarity_score, actions[])
  │              │        │ re-analyze                       │
  │              │        │◄──────────────────────────────────
  │              │        │ score acceptable? ──Yes──► exit loop, proceed
  │              │        │                  ──No, attempts<N──► loop
  │              │        │                  ──No, attempts=N──► exit loop, flag NEEDS_REVIEW
```
Rationale for a bounded loop (N=3 default, configurable per Product Definition): an unbounded repair loop risks infinite oscillation if a repair action and a validation check disagree about the fix; bounding it forces a `NEEDS_REVIEW` state (human decision) rather than a hang.

### 2.3 Plugin Discovery at Core Startup

```
Core Process Start
      │
      ▼
Plugin Engine scans products/*/product_definition.yaml
      │
      ▼
For each: run Product Definition Conformance Suite (§37) in-process
      │
      ├─ Pass ──► register in Plugin Registry, log INFO
      └─ Fail ──► log ERROR with validation detail, EXCLUDE from registry
                  (a broken plugin must not prevent Core from starting —
                   isolation of failure is a hard requirement, not a nicety)
      │
      ▼
Core API becomes available; /v1/products lists only successfully registered plugins
```

### 2.4 Quality Inspection (pre-export gate)

```
Adapter        Core API      Validation Engine   Machine Engine   Material Engine
  │ POST /jobs/{id}/quality-inspection │                  │                │
  │──────────────►│                    │                  │                │
  │                │ run_standard_checks(final_geometry)   │                │
  │                │───────────────────►│                  │                │
  │                │◄───────────────────│ ValidationReport │                │
  │                │ check_compatibility(machine, product) │                │
  │                │────────────────────────────────────►│                │
  │                │◄────────────────────────────────────│ Compatible?     │
  │                │ check_compatibility(material, product)                 │
  │                │─────────────────────────────────────────────────────►│
  │                │◄─────────────────────────────────────────────────────│
  │                │ + target-system export-integrity check (§ Error Model)│
  │                │ assemble PASS / WARNING / FAIL                        │
  │◄───────────────│ 200 OK { result: PASS|WARNING|FAIL, details[] }       │
```

---

## 3. Component Interaction Diagram (runtime call shape, distinct from static dependency graph in §1)

```
                 ┌─────────────┐
                 │   Adapter    │
                 └──────┬──────┘
                        │ synchronous request/response (REST)
                 ┌──────▼──────┐
                 │   Core API   │────────────┐
                 └──────┬──────┘             │ emits events (async, fire-and-forget)
                        │ orchestrates        ▼
                 ┌──────▼──────┐      ┌─────────────┐
                 │  Job/Workflow│      │  Event Bus   │
                 │  Orchestrator│      └──────┬──────┘
                 └──────┬──────┘             │ subscribed by
        ┌────────────────┼────────────────┐   ▼
        ▼                ▼                ▼  ┌─────────────┐ ┌──────────────┐
  [Pipeline Engines, synchronous, per §2.1]   │ Notification │ │ Logging/Audit  │
                                              │ Engine        │ │                │
                                              └─────────────┘ └──────────────┘
```
The key distinction: the analysis/repair/validation pipeline is **synchronous request/response** (the Adapter is waiting for an answer to show the operator); workflow-transition side effects (notify, log, update queue) are **asynchronous, published to the Event Bus** so a slow notification channel (e.g. a future email/webhook integration) never blocks the operator's UI.

---

## 4. API Contract Specifications (contract-level, not a full OpenAPI spec)

### 4.1 Conventions
- All endpoints versioned under `/v1/...`; a breaking change requires `/v2/...` (§25).
- Request/response bodies are JSON; geometry payloads embed the Neutral Geometry Format (§5) as a nested structure, never a separate binary blob.
- Every response includes a `correlation_id` (echoing the request's, or newly generated) for log correlation (§19).
- Every error response follows the Error Model envelope (§17), never a bare HTTP status with no body.

### 4.2 Endpoint groups (responsibility, not full route list)
| Group | Responsibility | Key operations (contract-level) |
|---|---|---|
| `/v1/products` | Plugin/Product Definition discovery | list registered products, get one product's schema |
| `/v1/geometry` | Neutral geometry utilities | validate-format, round-trip-check (diagnostic) |
| `/v1/analysis` | Run Manufacturing Analysis | analyze(geometry, product_type, material_id, machine_id) → AnalysisResult |
| `/v1/repair` | Run Automatic Repair | repair(geometry, product_type, tolerance) → RepairResult |
| `/v1/validation` | Run Geometry Validation standalone | validate(geometry, product_type) → ValidationReport |
| `/v1/presets` | Preset CRUD/list | list-for-product, get, (future) create/update |
| `/v1/machines` | Machine profile CRUD | list, get, recommend-settings(material_id, product_type) |
| `/v1/materials` | Material profile CRUD | list, get |
| `/v1/rules` | Knowledge Engine rule access | get-resolved(product_type, material_id, machine_id), get-version-history |
| `/v1/jobs` | Job lifecycle | create, get, list, update-status, attach-report |
| `/v1/workflow` | Workflow instance control | start, advance(event), get-state, get-definition |
| `/v1/queue` | Queue Manager | enqueue, get-status, transition, list-by-state |
| `/v1/reports` | Report generation | generate(job_id, template_ref) → Report |
| `/v1/notifications` | Notification config/history | list-channels, get-history-for-job |
| `/v1/enterprise` | Operators/customers/licensing | CRUD scoped to Option A (single-machine multi-operator) |

### 4.3 Idempotency
State-mutating endpoints (`enqueue`, `advance`, `update-status`) accept an optional `idempotency_key`; replaying the same key returns the original result rather than re-executing — necessary because the Adapter (VBA, over HTTP) has no reliable retry semantics of its own, and a naive retry-on-timeout could otherwise double-advance a workflow.

---

## 5. Neutral Geometry Format Specification

### 5.1 Design goal
A CAD-independent geometry representation that (a) round-trips losslessly to/from CorelDRAW's curve model within floating-point tolerance, (b) is human-inspectable for debugging, (c) doesn't require a binary parser.

### 5.2 Shape
```
NeutralGeometry {
  units: "mm"                     // always mm; Adapter converts CorelDRAW's internal units at the boundary
  bounding_box: { x, y, width, height }
  layers: [
    {
      layer_role: string          // "original" | "repair" | "male" | "female" | ... per Product Definition's layer_structure (v3 §8.2 item 7)
      objects: [
        {
          object_id: string       // stable across repair operations where possible, for diffing/audit
          subpaths: [
            {
              closed: boolean
              nodes: [
                { x: float, y: float, node_type: "line"|"curve", control_in: {x,y}|null, control_out: {x,y}|null }
              ]
            }
          ]
          fill: { type: "none"|"solid", color: string|null }   // manufacturing-relevant only (target-system color mapping), not full CDR styling
          stroke: { width: float|null }
        }
      ]
    }
  ]
  metadata: { source_adapter: string, source_file_hint: string|null, imported_at: timestamp }
}
```

### 5.3 Explicit non-goals
Not represented: fonts/text-as-text (text is always converted to curves before crossing the boundary — Core never reasons about typography), gradients, bitmaps, PostScript fills, layer visual styling beyond fill/stroke as above. These are CAD-presentation concerns, not manufacturing concerns, and stay on the Adapter side.

### 5.4 Round-trip contract
`Adapter.ShapeToNeutral()` and `Adapter.NeutralToShape()` (v2 §4) must satisfy: `NeutralToShape(ShapeToNeutral(s))` produces a shape whose node coordinates differ from `s` by no more than a configurable epsilon (default 0.001mm) and whose subpath count/closedness is unchanged. This contract is tested directly (§37) — it's the highest-risk seam in the whole system (v2 §11, row 2).

---

## 6. Product Definition Specification

```
ProductDefinition {
  product_type: string           // unique, e.g. "emboss_seal", stable identifier, never reused for a different product
  display_name: string
  version: semver string          // e.g. "1.2.0"
  rules: { categories: [string] }         // which Knowledge Engine categories this product declares (§9)
  validation_rules: { enabled_checks: [string], thresholds_ref: rule category name }
  repair_rules: { enabled_repairs: [string], max_attempts: int (default 3), similarity_tolerance: float }
  machine_compatibility: [ { machine_profile_id | machine_type_tag, constraint_notes: string } ]
  material_compatibility: [ { material_profile_id | material_type_tag, constraint_notes: string } ]
  output_formats: [string]        // e.g. ["dxf","svg","cdr","pdf","ai"]
  layer_structure: [ { role: string, default_name: string, required: boolean } ]
  presets: [ PresetDefinition ]
  report_templates: [ TemplateReference ]
  preview_templates: [ TemplateReference ]
  workflow_ref: WorkflowDefinition reference | null   // null = use platform default (§8)
}
```
**Validation on load:** a ProductDefinition failing schema validation, referencing a non-existent rule category, or declaring an unreachable workflow state is rejected at registration (§2.3), never partially loaded.

---

## 7. Plugin Contract Specification

```
ProductPlugin (paired 1:1 with a ProductDefinition by product_type) {
  get_default_rules() → RuleSet
  validate(geometry: NeutralGeometry, definition: ProductDefinition) → ValidationResult
      // product-specific judgment ON TOP OF the generic Validation Engine's checks —
      // e.g. "is this shape topologically valid for embossing," not a replacement for open-curve checks
  analyze(geometry, definition, resolved_rules, machine, material) → AnalysisResult
  repair(geometry, definition, resolved_rules) → RepairResult
  generate_outputs(geometry, definition, params) → OutputSet
  generate_preview(geometry, definition) → PreviewSet
  on_load() → void            // lifecycle hook, e.g. warm caches; must not perform I/O side effects beyond its own product folder
  on_unload() → void
}
```
**Contract discipline:** every method receives immutable inputs and returns new values — no method may mutate `geometry` in place, since the pipeline (§2.1–2.2) relies on being able to re-run analysis against the pre-repair geometry for comparison/rollback.

---

## 8. Workflow Definition Schema

```
WorkflowDefinition {
  workflow_id: string
  version: semver string
  states: [ { name: string, is_terminal: boolean, entry_actions: [ActionRef], exit_actions: [ActionRef] } ]
  transitions: [
    { from_state: string, to_state: string, on_event: string, guard: ConditionRef | null }
  ]
  initial_state: string
}
WorkflowInstance {
  instance_id: string
  workflow_ref: { workflow_id, version }
  job_id: string
  current_state: string
  history: [ { state, entered_at, event_that_arrived } ]
}
```
**Structural validation (enforced at registration, tested in §37):** every declared state must be reachable from `initial_state`, and every non-terminal state must have at least one outbound transition — a direct implementation of v3 §18's "no dead-end states" testing requirement.

---

## 9. Manufacturing Rule Schema

```
RuleCategory {
  category_name: string          // e.g. "bridge_width", "clearance" — open-ended per v3 §12.2
  version: int
  default: { <key>: <value> }
  material_overrides: { <material_id>: { <key>: <value> } }
  machine_overrides: { <machine_id>: { <key>: <value> } }
  product_overrides: { <product_type>: { <key>: <value> } }
}
ResolvedRuleSet {
  resolved_at: timestamp
  category_versions_used: { <category_name>: version int }   // recorded on every Job for reproducibility (v3 FR-7)
  values: { <category_name>: { <key>: <value> } }
  resolution_trace: [ { category, key, chosen_value, source: "product"|"machine"|"material"|"default" } ]
      // the resolution_trace is what makes Explainability (v2 §1.3) concrete — every threshold's
      // provenance is inspectable, not just its final value
}
```
Resolution order per v3 §12.3: `product_type override → material override → machine override → platform default`.

---

## 10. Material Schema

```
MaterialProfile {
  material_id: string
  display_name: string
  version: int
  thickness_mm: float
  hardness_notes: string | null
  spring_back_factor: float | null       // affects clearance recommendations, not mandatory for all materials
  compatible_machine_types: [string]
  rule_category_overrides: { <category_name>: {...} }   // feeds Rule Engine (§9)
}
```

---

## 11. Machine Schema

```
MachineProfile {
  machine_id: string
  display_name: string
  version: int
  machine_type: string             // "co2_laser" | "fiber_laser" | "uv_laser" | "rotary" | future
  kerf_mm: float
  power_speed_table: [ { material_id, power_pct, speed_mm_s, passes: int } ]
  target_systems: [string]         // e.g. ["rdworks"] — generalizes v1's RDWorks-specific assumption (v3 §1.3)
  rule_category_overrides: { <category_name>: {...} }
}
```

---

## 12. Job Schema

```
Job {
  job_id: string (UUID)
  product_type: string
  customer_id: string | null
  created_at, updated_at: timestamp
  status: "queued"|"running"|"paused"|"completed"|"failed"|"cancelled"   // Queue state (§15), distinct from workflow state
  workflow_instance_ref: string
  versions_used: {
    product_definition_version, workflow_version,
    rule_category_versions: {...} (from ResolvedRuleSet),
    material_version, machine_version, preset_version
  }
  geometry_refs: { original, repaired, male, female, ... }   // pointers, not inline blobs, for large jobs (§22)
  analysis_result_ref: string | null
  validation_reports: [ { stage: "pre-repair"|"quality-inspection", report_ref } ]
  report_refs: [string]
  operator_id: string | null
}
```
**Why `versions_used` is exhaustive rather than "just the rule version":** a reprint/warranty dispute six months later needs to reproduce the *exact* conditions a job was scored under, not just the rules — a material profile correction or a machine kerf recalibration after the fact would otherwise silently make old jobs unreproducible even with the right rule version pinned.

---

## 13. Asset Schema 🟡

```
Asset {
  asset_id: string
  asset_type: "logo"|"font"|"template"|"icon"|"border"|"standard_design"|"machine_profile_ref"|"material_profile_ref"|"preset_library"
  storage_ref: string          // file path or blob store key — storage backend is an implementation detail, not fixed here
  tags: [string]
  version: int
  created_by: operator_id | null
}
```
Marked 🟡 per v3: schema drafted for completeness; not built until validated by a second real product's asset needs (v3 §0.2).

---

## 14. Report Schema

```
Report {
  report_id: string
  job_id: string
  template_ref: TemplateReference
  generated_at: timestamp
  sections: [
    { section_type: "summary"|"parameters"|"validation"|"warnings"|"recommendations", content: {...} }
  ]
  format: "pdf"|"html"          // pdf is the committed target; html is a cheap-to-support byproduct of template rendering
  pass_fail: "PASS"|"WARNING"|"FAIL" | null
}
```

---

## 15. Queue Schema

```
QueueEntry {
  job_id: string
  state: "queued"|"running"|"paused"|"completed"|"failed"|"cancelled"
  priority: int (default 0)
  assigned_operator_id: string | null
  enqueued_at, started_at, finished_at: timestamp | null
  state_history: [ { state, changed_at, changed_by } ]
}
```
Reiterating v3 §14.5: QueueEntry.state is intentionally a separate state machine from WorkflowInstance.current_state — a job can be QueueEntry.state = "queued" while WorkflowInstance.current_state = "Customer Approval" (waiting on the customer, not on the queue).

---

## 16. Notification Schema

```
NotificationEvent {
  event_id: string
  event_type: string            // "job.state_changed" | "validation.failed" | "queue.status_changed" | ...
  payload: {...}                 // event-type-specific
  emitted_at: timestamp
  channels_attempted: [ { channel: "in_app"|"email"|"sms"|"webhook", status: "delivered"|"failed"|"pending", attempted_at } ]
}
```
v1 build target: `in_app` only. Schema includes the other channels as documented-but-unbuilt extension points (v3 FR-13), consistent with not over-building ahead of demand.

---

## 17. Error Model

### 17.1 Response envelope (every non-2xx API response)
```
ErrorResponse {
  correlation_id: string
  error_code: string         // stable, machine-readable, e.g. "RULE_RESOLUTION_FAILED"
  category: "validation"|"not_found"|"conflict"|"security"|"internal"|"plugin_error"
  message: string             // human-readable, safe to show an operator
  details: [ { field, issue } ] | null
  retryable: boolean
}
```

### 17.2 Design rationale
`error_code` is the contract the Adapter programs against (stable string), `message` is display-only and may be reworded across versions without being a breaking change — this distinction avoids the common failure mode where UI code fragile-matches on human text.

---

## 18. Exception Hierarchy (Core-internal, maps to §17's error_code at the API boundary)

```
PlatformException (base)
 ├── ValidationException          → category: validation
 │    ├── GeometryFormatException      // malformed Neutral Geometry input
 │    └── RuleThresholdViolation
 ├── ResolutionException          → category: internal or validation
 │    ├── RuleResolutionException      // e.g. conflicting overrides, missing category
 │    └── ProductDefinitionLoadException
 ├── PluginException              → category: plugin_error
 │    ├── PluginConformanceException   // failed registration checks (§2.3)
 │    └── PluginRuntimeException       // raised during validate/analyze/repair/generate_*
 ├── CompatibilityException       → category: validation
 │    ├── MachineCompatibilityException
 │    └── MaterialCompatibilityException
 ├── WorkflowException            → category: conflict or validation
 │    ├── InvalidTransitionException
 │    └── UnreachableStateException    // caught at registration, §8
 ├── SecurityException            → category: security
 │    ├── AuthenticationException
 │    └── AuthorizationException
 └── PersistenceException         → category: internal
      ├── JobNotFoundException         → category: not_found
      └── VersionConflictException     // optimistic concurrency conflict, §23
```
**Rule:** every exception thrown across an engine boundary must be one of the above (or a subclass) — a raw/unclassified exception reaching the API layer is treated as a defect (caught by a catch-all that logs at ERROR and returns a generic `internal` error, never a stack trace to the Adapter).

---

## 19. Logging Specification

```
LogEntry {
  timestamp: ISO8601
  level: "DEBUG"|"INFO"|"WARNING"|"ERROR"|"CRITICAL"
  component: string          // engine/module name
  correlation_id: string | null
  job_id: string | null
  message: string
  context: {...}             // structured extra fields, engine-specific
}
```
- **Destinations:** local rotating file (per-day) always; per-job log excerpt also written to the Job's own log folder (v1 §"Deliverables" precedent) for QA/reprint traceability.
- **Levels in practice:** INFO for every stage transition and API call; WARNING for validation/quality-inspection non-fatal issues; ERROR for caught PlatformExceptions; CRITICAL reserved for startup failures (e.g., Core can't bind its port, database unreachable).
- **Retention:** 90 days rotating by default, configurable (§20) — job-scoped logs retained as long as the Job record itself (tied to backup/recovery policy, §26).

---

## 20. Configuration Specification

```
CoreConfig {
  api: { bind_host: "127.0.0.1" (never 0.0.0.0 per v3 §17.2), port: int, auth_token_path: string }
  data: { sqlite_path: string, backup_dir: string }
  logging: { level, retention_days, log_dir }
  pipeline: { repair_max_attempts_default: int, similarity_tolerance_default: float }
  plugins: { products_dir: string }
}
```
**Precedence (highest to lowest):** per-job override (persisted with the Job, §12) → environment variables → `config.yaml` file → built-in defaults. This mirrors v2 §2.4's settings precedent, generalized to Core-level config rather than just manufacturing tolerances.

---

## 21. Performance Targets

| Operation | Target | Note |
|---|---|---|
| Typical artwork (<5,000 nodes) full analyze+score | <2s | Carried from v1 NFR, now measured at the Core API boundary, excluding Adapter-side CorelDRAW automation time |
| Complex artwork (<30,000 nodes) full analyze+score | <8s | |
| Repair loop (up to 3 attempts) on complex artwork | <15s total | |
| API round-trip overhead (localhost) | <50ms p95, excluding engine compute time | Sets the ceiling below which HTTP-as-IPC (v2 §11 risk) is considered validated |
| Batch job (per file), Core-side processing only | <10s | Adapter/CorelDRAW automation time is the actual batch bottleneck (v2 §16), not counted here |

These are **targets to validate against**, not guarantees — first real measurement happens in Phase 1/2 spikes (v2 §8) and this table should be revisited with real numbers before being treated as a commitment.

---

## 22. Memory Considerations

- **Geometry payloads are not memory-mapped/streamed for v1** — a 30,000-node artwork as JSON is a few MB at most, well within acceptable single-request payload size; revisit only if a real product needs orders-of-magnitude larger geometry.
- **Job records reference geometry by storage pointer (§12), not inline** — prevents the Job table itself from growing unboundedly as job history accumulates, keeping Job listing/query operations fast regardless of how many jobs have run.
- **Batch processing (v2 §6.2) processes one file at a time** — no requirement to hold multiple jobs' geometry in memory simultaneously, consistent with the sequential-not-parallel batch model already decided.
- **Asset library (§13, 🟡)** — when built, must be paginated/queried, never loaded wholesale into memory; flagged now so the eventual schema (§13) isn't designed in a way that assumes small total asset count.

---

## 23. Concurrency Model

- **Core handles concurrent HTTP requests** (standard async web framework request handling) but **serializes access per-Job** — a job-level lock (or optimistic versioning, see `VersionConflictException` §18) prevents two concurrent requests from advancing the same WorkflowInstance inconsistently.
- **The Adapter is effectively single-threaded from Core's perspective** — CorelDRAW automation is inherently one-document-at-a-time (v2 §6.2), so Core does not need to support multiple simultaneous *analyze* calls from the same Adapter instance; it does need to support multiple **different** Adapter instances (future multi-operator, v3 §14.5) each working a different job concurrently.
- **Workflow transitions are transactional**: `advance(instance, event)` either fully applies (state changed, history appended, event emitted) or fully fails — no partial transition is ever observable.

---

## 24. Serialization Format

- **Wire format:** JSON everywhere across the API boundary (§4), including embedded Neutral Geometry (§5) — no binary formats over the API, for debuggability and because VBA's HTTP/JSON handling is already a known risk area (v2 §11) not worth compounding with a binary codec.
- **On-disk format for definitions/rules:** YAML (human-editable, diff-friendly in git — v3 §13.1's Knowledge Base rationale extended to Product Definitions and Workflow Definitions uniformly).
- **On-disk format for job/operational data:** SQLite (v2 §16.2), not JSON files — this is transactional operational data, not human-authored configuration, and the two should not be conflated.

---

## 25. Versioning Strategy

- **API:** semantic path versioning (`/v1`, `/v2`); additive fields never require a version bump; removed/repurposed fields always do (v2 §10 coding standards, carried forward).
- **ProductDefinition / WorkflowDefinition / RuleCategory / MaterialProfile / MachineProfile:** each independently semver'd (§6–11); a Job pins the exact version of each it was processed under (§12).
- **Neutral Geometry Format:** versioned via a `format_version` field (added to §5.2's top-level object, omitted above for brevity but required) so a future format change doesn't silently corrupt older stored geometry.
- **Plugin contract (§7):** versioned as part of Architecture, not TDD — a breaking change to `IProductPlugin` itself is an architectural event requiring re-review of both existing plugins, not a routine version bump.

---

## 26. Backup Strategy

- **What's backed up:** SQLite data file (jobs, customers, operators, queue, versions metadata), the `products/*/` definition trees (also in git, but the runtime copy must match what actually ran), and the Knowledge Base rule YAML files.
- **Schedule:** daily automatic snapshot (configurable, §20) plus an on-demand snapshot trigger before any bulk rule/definition edit.
- **Retention:** rolling 30 daily snapshots by default; older snapshots pruned unless explicitly pinned (e.g., "before this major rule change").
- **Format:** a timestamped copy-on-write style archive (e.g., a zipped snapshot directory) rather than continuous replication — appropriate at Option A's single-machine scale (v2 §0.4); revisit if Option B (cloud, v2 §17/v3 §21) is ever built.

---

## 27. Recovery Strategy

- **Crash recovery:** on Core restart, any WorkflowInstance not in a terminal state is reloaded from its last persisted state (§8) — no job silently disappears; the Adapter's next poll/query picks up exactly where the crash occurred.
- **Corrupted definition/rule file:** Plugin Engine's registration-time validation (§2.3) means a corrupted YAML file fails to register cleanly (logged ERROR) rather than crashing Core or silently applying a partially-parsed rule set.
- **Settings recovery:** Configuration (§20) falls back to built-in defaults if `config.yaml` is missing/corrupt, logging a CRITICAL so the condition is visible rather than silently masked.
- **Job recovery (mid-repair-loop crash):** because each repair attempt's intermediate geometry is persisted as a checkpoint (extending v1/v2's page-duplication checkpoint concept to Core-side geometry storage), a crash mid-loop resumes from the last completed attempt, not from scratch.

---

## 28. Security Model
(Restates and operationalizes v3 §17; nothing new architecturally, made concrete here.)

- Local API bound to `127.0.0.1` only (§20 config).
- All requests require a bearer token (§29).
- Data at rest: SQLite file encrypted (implementation detail deferred, e.g. SQLCipher or OS-level volume encryption — either satisfies the requirement; not prescribing one here since it doesn't affect the architecture).
- Rule/definition version records are append-only and checksummed (v3 §17.5) — enforced by the persistence layer rejecting any UPDATE to a historical version row, only INSERTs of new versions.

---

## 29. Authentication Flow

```
Core starts
  │
  ▼
Generate a fresh local auth token (random, high-entropy), write to auth_token_path (§20, file permissions restricted to the current user)
  │
  ▼
Adapter starts, reads token from the same file (both processes run as the same local user — no network transmission of the token)
  │
  ▼
Every Adapter → Core request includes `Authorization: Bearer <token>`
  │
  ▼
Core rejects (401, AuthenticationException) any request missing/mismatching the token
  │
  ▼
Token rotates on every Core restart — an Adapter session from a previous Core process cannot replay old requests
```
This is deliberately simple (no OAuth/session complexity) because the trust boundary is "same machine, same local user," not a network trust boundary — over-engineering this for Option A would be solving Option B's (cloud) problem prematurely.

---

## 30. Authorization Model

- **Operator roles (Option A scope):** `admin` (full access, including rule/definition edits), `operator` (run jobs, cannot edit rules/definitions/machine profiles), `viewer` (read-only, e.g. for a supervisor checking dashboards).
- **Permission matrix** applied at the API route-group level (§4.2): e.g. `/v1/rules` write operations require `admin`; `/v1/jobs` create/advance require `operator` or above; all `GET` routes available to `viewer` and above.
- **Plugin tier interaction (v3 §17.3):** authorization is orthogonal to plugin trust tier — an `operator` role can run jobs against any *registered* plugin regardless of tier, but only `admin` can trigger plugin registration/re-registration, since that's where Tier 2/3 review matters.

---

## 31. Plugin Lifecycle

```
DISCOVERED → VALIDATING → (PASS) → REGISTERED → LOADED → ACTIVE
                 │
                 └─(FAIL)→ REJECTED (logged, excluded, Core continues — §2.3)

ACTIVE → DEACTIVATED (e.g. admin disables a product temporarily) → LOADED (can reactivate)
ACTIVE/LOADED → UNREGISTERED (definition file removed) → DISCOVERED (if re-added, re-validates from scratch)

Version upgrade (new product_definition.yaml version dropped in products/x/):
  DISCOVERED (new version) → VALIDATING → REGISTERED as a NEW version alongside the old one
  (existing Jobs keep referencing their pinned version, §12; new Jobs get the latest by default)
```

---

## 32. Event System

- **Internal event bus:** in-process publish/subscribe (not a separate message broker at Option A scale — that would be over-engineering for a single-machine service).
- **Published events (non-exhaustive, extensible):** `job.created`, `workflow.transitioned`, `validation.failed`, `quality_inspection.completed`, `queue.state_changed`, `plugin.registered`, `plugin.rejected`.
- **Subscribers:** Notification Engine (fans out to channels, §16), Logging (every event logged at INFO minimum), future Audit trail consumer.
- **Guarantee:** at-least-once delivery to subscribers within the same process; no durability guarantee across a Core crash for in-flight events (acceptable since the underlying state change — e.g. the WorkflowInstance transition itself — is what's durably persisted, §27; the event is a notification of that fact, not the fact itself).

---

## 33. Internal Message Flow (representative case: Analyze request, showing sync vs. async split)

```
1. Adapter → Core API: POST /v1/analysis  [SYNCHRONOUS]
2. Core API → Plugin Engine → Rule Engine → Validation Engine → Analysis Engine  [SYNCHRONOUS chain, §2.1]
3. Core API → Adapter: 200 OK with AnalysisResult  [SYNCHRONOUS response]
4. Core API → Event Bus: publish "analysis.completed" event  [ASYNC, fire-and-forget, happens after step 3's response is already prepared — never delays the operator-facing response]
5. Event Bus → Logging subscriber: log INFO  [ASYNC]
6. Event Bus → Notification subscriber: check if any configured channel cares about this event type  [ASYNC]
```
The design principle: **anything the operator is waiting to see is synchronous; anything that's bookkeeping/side-effect is asynchronous** — this is what keeps a slow or misbehaving Notification channel from ever becoming a perceived Core hang.

---

## 34. Folder Structure Refinement (extends v3 §3)

```
PMS/
├── core/
│   ├── ... (unchanged from v3 §3)
│   ├── schemas/                     # NEW — JSON Schema / formal versions of §5-16 of this TDD
│   │   ├── neutral_geometry.schema.json
│   │   ├── product_definition.schema.json
│   │   ├── workflow_definition.schema.json
│   │   ├── job.schema.json
│   │   └── ... (one per schema section above)
│   ├── contracts/                   # already existed in v3; TDD adds:
│   │   ├── error_model.md
│   │   └── exception_hierarchy.md
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── regression/
│           └── baselines/           # NEW — golden-output snapshots per test doc, §39
```

---

## 35. Naming Conventions

- **IDs:** UUIDv4 for all runtime entities (Job, WorkflowInstance, QueueEntry, NotificationEvent, Asset); human-authored definitions (ProductDefinition, WorkflowDefinition, RuleCategory, MachineProfile, MaterialProfile) use a stable slug (`emboss_seal`, `co2_laser_80w_unit2`) plus a separate semver version field — slugs are permanent identity, versions track change.
- **Wire format field names:** `snake_case` throughout the JSON API, matching the schemas in §5–16 exactly (no translation layer between API JSON and internal schema naming — reduces a whole class of mapping bugs).
- **Event type names:** `noun.past_tense_verb` (`job.created`, `workflow.transitioned`) — consistent, greppable in logs.
- **Error codes:** `SCREAMING_SNAKE_CASE`, stable once shipped (§17.2) — never renamed, only deprecated alongside a new code if semantics change.

---

## 36. Coding Standards (extends v2 §10, restated for Core-as-language-agnostic-target)

- Every public Core interface (§4, §7) must have its contract documented in the schemas/contracts folders (§34) *before* an implementing function is written — the TDD's job is to make this possible; the coding standard's job is to keep it true during implementation.
- Type annotations mandatory in whatever language implements a given Core module (Python type hints today, per v2 §2.4's language choice) — this is what keeps §25's "migrate without redesign" claim mechanical rather than aspirational.
- No engine may catch a `PlatformException` subclass and re-raise a different, unrelated one — exception translation only happens at defined boundaries (API layer translating to `ErrorResponse`, §17), preserving the hierarchy's diagnostic value.
- Adapter-side (VBA) standards unchanged from v2 §10: no manufacturing threshold/formula/decision in any Adapter class, full stop.

---

## 37. Unit Testing Strategy

- Every engine in §1's dependency graph gets isolated unit tests using fixture `ProductDefinition`/`ProductPlugin`/`RuleSet` objects — never real product plugins — so engine tests don't break when a product plugin changes.
- **Static import-graph test** enforces §1's "no upward dependency" rule automatically (fails CI if e.g. Geometry Engine imports Analysis Engine).
- **Neutral Geometry round-trip test** (§5.4) runs against a fixture library of representative shapes (simple polygon, compound path, nested subpaths, curve-heavy signature-style path) — independent of any real CorelDRAW file, using synthetic neutral-format fixtures plus, once the Adapter exists, real round-trips through actual CorelDRAW shapes.
- **Workflow structural validation test** (§8, §31): fixture WorkflowDefinitions including a deliberately broken one (unreachable state) to confirm registration correctly rejects it.

## 38. Integration Testing Strategy

- **Adapter↔Core contract tests:** run against Core's actual OpenAPI-documented endpoints (not mocks), validating real HTTP/JSON behavior — this is where v2 §11's "VBA HTTP client proves clunky" risk gets caught early, per the Phase 2 spike already planned.
- **Plugin conformance integration:** a real plugin (Emboss Seal, then Rubber Stamp once built) run through the full §2.1–2.4 sequence end-to-end against Core, not just unit-tested in isolation.
- **Cross-engine integration:** the repair loop (§2.2) tested as a whole against fixture geometries designed to require exactly 1, exactly N (max), and 0 repair attempts — validating the bounded-loop behavior itself, not just each engine individually.

## 39. Regression Testing Strategy

- **Golden-output baselines** (§34's `baselines/` folder): for each curated test document (v1 §12's government seal, church logo, signature, corrupted file, extended per v2/v3 with Rubber Stamp equivalents once that plugin exists), a saved AnalysisResult + ValidationReport + RepairResult is checked into the repo; any Core change that alters these outputs on unchanged inputs fails CI and requires explicit human sign-off that the change is intentional (a rule-set version bump, say) rather than an accidental regression.
- **Cross-plugin regression** (v3 §18): once two plugins exist, every Core engine change runs against both plugins' full fixture sets — this is the concrete mechanism that catches "fixed for Emboss Seal, broke Rubber Stamp."
- **Determinism check** (v2 §1.3 NFR): the same fixture run twice must produce byte-identical results; a regression test that runs each fixture twice and diffs is cheap insurance against accidental non-determinism (e.g., unordered dict iteration leaking into output ordering).

## 40. Deployment Architecture

```
Target machine (Windows, shop floor)
 ├── CorelDRAW X7 + EmbossSealPro/PMS Adapter (.gms macro project)
 │      — installed via CorelDRAW's standard macro/VBA project loading
 └── PMS Core (local Windows process)
        — packaged as a standalone executable (e.g., PyInstaller-built, so the
          target machine doesn't need a separate Python install — an
          implementation detail, not an architectural commitment)
        — registered to start automatically (Windows service or a startup-folder
          launcher — either satisfies "Core is running before the Adapter needs it")
        — writes its SQLite data file, logs, and backups to a fixed local
          AppData-style path (§20 config)
```
- **Update model (Option A scope):** manual replace-and-restart of the Core executable and the `.gms` package; no auto-update infrastructure built now (explicitly deferred to v3 §21's "Far" horizon, consistent with v2 §17's cloud-phase scoping).
- **Rollback:** because Core's data layer is versioned/backed-up (§25–26) and the executable is a single replaceable file, rollback is "restore previous executable + restore the pre-update backup snapshot if the data schema changed" — no in-place migration tooling is being built for v1, since there's only ever one shop-floor machine to manage at Option A scale.

---

## Summary — What This TDD Locks In vs. Leaves Open

**Locked in (implementation should treat as given):** all schemas (§5–16), the error/exception model (§17–18), the API contract shape (§4), the plugin lifecycle (§31), and the sync/async split (§33) — these are the load-bearing contracts Phase 1–2 code directly against.

**Left open, deliberately:** exact storage backend for encryption-at-rest (§28), exact packaging tool for Core's executable (§40), and anything schema'd but marked 🟡/🔴 in Architecture v3 (Asset Management §13, Template Engine references throughout, Extension SDK Tier 3) — these have a documented shape so a future implementer isn't starting from nothing, but are not being built now.

No further architectural changes are proposed here — where this TDD needed a decision Architecture v3 didn't make (e.g., idempotency keys in §4.3, the bounded repair-loop count in §2.2), I've made the smallest decision consistent with v3's stated principles rather than reopening architecture. Flag any of those you'd like elevated back to an architectural decision instead.

Once you approve this TDD, implementation planning (breaking Phase 1/2 of the roadmap into concrete work items) is the natural next step — still no code until you say so.
