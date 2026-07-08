# PMS — Manufacturing Automation Platform
### Architecture & Planning Document (v3.0)

**Provisional name:** using "PMS" (Platform Manufacturing Suite) below purely as a label — rename freely.
**Status:** Pre-development, revision 3. Architecture only — no Python, VBA, or API code in this document, per your instruction.
**Relationship to v2:** Supersedes v2 wherever product-specific (embossing-seal) assumptions leaked into what should have been generic Core design. v2's Core/Adapter split (§0.2 of that document) is preserved and is now applied more strictly.

---

## 0. Framing: What Actually Changed, and a Challenge Back

### 0.1 The real shift
v2 had a Core that was *architecturally* product-independent but still *conceptually* shaped around embossing (its engines were named "Manufacturing Analysis," "Emboss Preview Simulator," etc., with embossing as the assumed product). v3 makes every engine genuinely product-blind: the Core knows about geometry, rules, machines, materials, workflows, and jobs — it does not know what an "embossing seal" or a "rubber stamp" *is*. That knowledge moves entirely into Product Definitions (§8).

### 0.2 A challenge before I proceed
You've asked me to design this as a 10–15 year platform and to generalize everything now — Product Definition Engine, Workflow Engine, Template Engine, Asset Management, Extension SDK, Queue Manager, all of it. I'll do that below, because you asked for the architecture, not an opinion on sequencing. But I want to name the trade-off plainly rather than silently absorb it:

**Every engine here is being designed against exactly one working example (Emboss Seals) and one planned-but-unbuilt example (Rubber Stamp).** Software designed for generality from a single concrete case reliably guesses wrong about which parts are actually reusable and which parts only look reusable. The standard mitigation — "rule of three," don't generalize an abstraction until you have three real cases pulling on it — argues for building Emboss Seals and Rubber Stamp as full plugins *before* over-investing in, say, the Extension SDK's third-party plugin lifecycle or the Template Engine's cross-product template format, both of which are currently speculative.

I'm not refusing to design them — they're specified in full below. I'm flagging that **§8's Product Definition contract is the one piece of this document I'd treat as load-bearing and worth getting right before building further; several of the "Engine" sections (Template, Asset Management, Extension SDK, Queue Manager) are lower-confidence and should be expected to change shape once Rubber Stamp exists as a second real data point.** I've marked confidence levels per section accordingly. If you'd rather I design *only* the load-bearing core now and treat the rest as sketches to revisit, say so — otherwise I'm giving everything full treatment as requested.

### 0.3 Confidence key used throughout
- 🟢 **High confidence** — validated by two design passes (v1→v2) and general software architecture practice, not just this platform's specifics.
- 🟡 **Medium confidence** — sound in principle, shape will likely shift once Rubber Stamp is built.
- 🔴 **Speculative** — genuinely unproven at this stage; documented because requested, but treat as a first draft, not a commitment.

---

## 1. Software Requirements Specification (v3)

### 1.1 Purpose (revised)
PMS is a product-independent manufacturing automation platform. It analyzes, validates, repairs, previews, and exports manufacturing artwork for laser-based (and future non-laser) production processes, driven entirely by pluggable Product Definitions. It has no built-in knowledge of any specific product — Embossing Seals is Plugin #1, not a platform feature.

### 1.2 Functional Requirements (net-new/generalized over v2)

| ID | Requirement | Confidence |
|---|---|---|
| FR-1 | Core exposes generic Geometry, Rule, Validation, Analysis, Repair, Machine, Material, Reporting, Workflow, Plugin, Template, Asset, Queue, Notification, and Enterprise services, none referencing any specific product | 🟢 |
| FR-2 | A Product Definition fully describes a manufacturable product: rules, validation rules, repair rules, machine/material compatibility, output formats, layer structure, presets, report/preview templates (§8) | 🟢 |
| FR-3 | Core loads a Product Definition at runtime and configures itself accordingly — adding a new product requires zero Core changes | 🟢 |
| FR-4 | Every job proceeds through a configurable Workflow (state machine) rather than a hardcoded sequence (§10) | 🟡 |
| FR-5 | Reusable Assets (logos, fonts, templates, icons, borders, standard designs, machine/material profiles, preset libraries) are stored centrally and shared across products (§ Asset Management) | 🟡 |
| FR-6 | A Geometry Validation Engine runs a standard defect checklist (open curves, duplicate nodes/objects, self-intersections, min gap/bridge/wall, floating islands, tiny holes, node density, sharp angles, disconnected objects) and produces a structured validation report, independent of any specific product's manufacturing meaning for those defects | 🟢 |
| FR-7 | Every manufacturing rule, material, machine profile, and preset is independently versioned; every job records the exact versions used, for full reproducibility | 🟢 |
| FR-8 | A Quality Inspection module runs before export, producing PASS/WARNING/FAIL against rules, machine compatibility, material compatibility, output geometry, export integrity, and target-system compatibility (e.g. RDWorks, but generalized — see §1.3) | 🟢 |
| FR-9 | A Production Queue Manager tracks Queued/Running/Paused/Completed/Failed/Cancelled jobs, supporting future multiple concurrent operators | 🟡 |
| FR-10 | Automatic backup, version history, undo checkpoints, and crash/settings/job recovery | 🟡 |
| FR-11 | An Extension SDK exposes Geometry/Rule/Machine/Material/Reporting/Workflow APIs and a defined plugin lifecycle for third-party developers | 🔴 |
| FR-12 | A Template Engine supports reusable, product-agnostic templates (§ Template Engine) | 🟡 |
| FR-13 | A Notification Engine emits events (job state changes, validation failures, queue status) to configurable channels (initially in-app; email/SMS/webhook are natural but unbuilt extensions) | 🟡 |

### 1.3 One terminology correction I'm making
"RDWorks-ready" as a Core concept doesn't survive genericization — RDWorks is specific to laser-cutting output, and PMS must also support (per your product list) rotary engraving, fiber laser, and non-laser future products with entirely different downstream tools. I'm generalizing FR-8's "RDWorks compatibility" into **"Target System Compatibility,"** where "RDWorks" becomes one configured target system among others, defined per-Product-Definition (§8) or per-Machine-Profile (§ Machine Engine), not hardcoded into the Quality Inspection module.

---

## 2. System Architecture (v3)

### 2.1 Layering (supersedes v2 §2.1)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CAD/UI Adapters                               │
│   CorelDRAW Adapter (VBA) — today's only adapter                       │
│   [future: Illustrator Adapter, native Web UI, etc. — same contract]   │
└──────────────────────────────┬──────────────────────────────────────────┘
                                │  Adapter API (generalization of v2's Connector API)
┌──────────────────────────────▼──────────────────────────────────────────┐
│                          PMS CORE  (product-blind)                       │
│                                                                            │
│  ┌─────────────────┐ ┌─────────────────┐ ┌──────────────────────┐        │
│  │ Geometry Engine   │ │ Manufacturing    │ │ Geometry Validation   │        │
│  │                    │ │ Rule Engine       │ │ Engine                │        │
│  └─────────────────┘ └─────────────────┘ └──────────────────────┘        │
│  ┌─────────────────┐ ┌─────────────────┐ ┌──────────────────────┐        │
│  │ Manufacturing     │ │ Automatic Repair   │ │ Manufacturing          │        │
│  │ Analysis Engine    │ │ Engine             │ │ Knowledge Engine        │        │
│  └─────────────────┘ └─────────────────┘ └──────────────────────┘        │
│  ┌─────────────────┐ ┌─────────────────┐ ┌──────────────────────┐        │
│  │ AI Recommendation  │ │ Machine Engine      │ │ Material Engine         │        │
│  │ Engine              │ │                     │ │                          │        │
│  └─────────────────┘ └─────────────────┘ └──────────────────────┘        │
│  ┌─────────────────┐ ┌─────────────────┐ ┌──────────────────────┐        │
│  │ Reporting Engine    │ │ Plugin Engine        │ │ Workflow Engine          │        │
│  └─────────────────┘ └─────────────────┘ └──────────────────────┘        │
│  ┌─────────────────┐ ┌─────────────────┐ ┌──────────────────────┐        │
│  │ Template Engine     │ │ Asset Management     │ │ Queue Management         │        │
│  │                      │ │ Engine               │ │ Engine                   │        │
│  └─────────────────┘ └─────────────────┘ └──────────────────────┘        │
│  ┌─────────────────┐ ┌───────────────────────────────────────────┐        │
│  │ Notification Engine │ │ Enterprise Services (operators, customers,│        │
│  │                      │ │ licensing, backup/recovery, quality        │        │
│  │                      │ │ inspection, security)                      │        │
│  └─────────────────┘ └───────────────────────────────────────────┘        │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  Product Definition Loader  ──loads──►  [Emboss Seal Definition]      │    │
│  │  (Plugin Engine's registry)              [Rubber Stamp Definition]     │    │
│  │                                          [...future definitions]       │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────────────┘
```

### 2.2 The one rule that makes this honest
**No engine listed above may import, reference, or contain a conditional branch on a product-type string or product name.** Every product-specific decision is data (a Product Definition, §8) or delegated behavior (a Plugin implementing the Product Definition contract), never code inside an Engine. This is stricter than v2's equivalent rule (v2 §2.3, §10 coding standards) because v2 still allowed "product_type" as a parameter threaded through Core methods; v3 requires that parameter to resolve to a loaded Product Definition object immediately at the API boundary, so no Engine internals ever pattern-match on it again.

### 2.3 What an "Adapter" is now (generalizing v2's Connector)
v2's `CorelDrawConnector` becomes the first of potentially several **CAD/UI Adapters**. The Adapter contract (geometry serialization, CAD-native fast-path operations, layer management, export triggering) is unchanged in spirit from v2 §2–4, just renamed and explicitly designed to admit a second adapter later without Core changes. 🟢 High confidence — this part of v2 was already sound.

---

## 3. Folder Structure (v3)

```
PMS/
├── core/                                  # product-blind, CAD-independent
│   ├── api/
│   │   ├── v1/
│   │   │   ├── routes_geometry.*
│   │   │   ├── routes_rules.*
│   │   │   ├── routes_validation.*
│   │   │   ├── routes_analysis.*
│   │   │   ├── routes_repair.*
│   │   │   ├── routes_knowledge.*
│   │   │   ├── routes_ai.*
│   │   │   ├── routes_machines.*
│   │   │   ├── routes_materials.*
│   │   │   ├── routes_reporting.*
│   │   │   ├── routes_plugins.*
│   │   │   ├── routes_workflow.*
│   │   │   ├── routes_templates.*
│   │   │   ├── routes_assets.*
│   │   │   ├── routes_queue.*
│   │   │   ├── routes_notifications.*
│   │   │   └── routes_enterprise.*
│   │   └── openapi.yaml
│   ├── engines/
│   │   ├── geometry/
│   │   ├── rule_engine/
│   │   ├── validation/
│   │   ├── analysis/
│   │   ├── repair/
│   │   ├── knowledge/
│   │   ├── ai_recommendation/
│   │   ├── machine/
│   │   ├── material/
│   │   ├── reporting/
│   │   ├── plugin/                        # includes Product Definition Loader
│   │   ├── workflow/
│   │   ├── template/
│   │   ├── asset_management/
│   │   ├── queue/
│   │   └── notification/
│   ├── enterprise/
│   │   ├── operators/
│   │   ├── customers/
│   │   ├── licensing/
│   │   ├── security/                       # authn/authz, plugin sandboxing, audit
│   │   ├── backup_recovery/
│   │   └── quality_inspection/
│   ├── contracts/                          # the load-bearing interfaces, §8/§9
│   │   ├── product_definition_contract.*
│   │   ├── plugin_lifecycle_contract.*
│   │   └── extension_sdk_contract.*
│   ├── data/
│   │   └── models.*                        # Job, Customer, Operator, RuleVersion,
│   │                                        # MachineProfile, MaterialProfile,
│   │                                        # ProductDefinitionVersion, WorkflowInstance
│   └── tests/
│
├── products/                               # Product Definitions — data + product-specific code
│   ├── emboss_seal/                        # Plugin #1 — migrated from v2's Core content
│   │   ├── product_definition.yaml
│   │   ├── validation_rules.yaml
│   │   ├── repair_rules.yaml
│   │   ├── presets/                        # Pocket/Common/Corporate/Library/Doctor/... (v2 §"Production Presets")
│   │   ├── report_templates/
│   │   ├── preview_templates/
│   │   └── plugin_code/                    # product-specific logic implementing the contract
│   ├── rubber_stamp/                       # Plugin #2 — the validation case, §0.2
│   │   └── (same shape as emboss_seal/, populated when built)
│   └── _template/                          # scaffold for new product plugins
│
├── adapters/
│   └── coreldraw/                          # formerly "connector" — same content as v2 §3
│       └── (unchanged in shape from v2)
│
├── docs/
│   ├── SRS.md
│   ├── ArchitectureDiagrams/
│   ├── ProductDefinitionAuthoringGuide.md   # for building product #3 onward
│   └── ExtensionSDK/
│       └── (public docs for future third-party developers)
└── CHANGELOG.md
```

Note the structural statement this makes: `core/` has no subfolder for any product, ever; `products/` is where all product-specific knowledge lives, including Emboss Seal's — which is now architecturally identical in status to a plugin nobody's built yet.

---

## 4. Class Diagram (v3 — contracts only, no implementation language)

```
[Contract] ProductDefinition
  identity: product_type, display_name, version
  rules: ManufacturingRuleSet reference
  validation_rules: ValidationRuleSet reference
  repair_rules: RepairRuleSet reference
  machine_compatibility: [MachineProfile references + constraints]
  material_compatibility: [MaterialProfile references + constraints]
  output_formats: [format identifiers]
  layer_structure: [layer role → name mapping]
  presets: [PresetDefinition]
  report_templates: [TemplateReference]
  preview_templates: [TemplateReference]
  workflow: WorkflowDefinition reference (§10)

[Contract] ProductPlugin  (behavior; pairs with a ProductDefinition)
  validate(geometry, definition) → ValidationResult
  analyze(geometry, definition, machine, material) → AnalysisResult
  repair(geometry, definition) → RepairResult
  generate_outputs(geometry, definition, params) → OutputSet
  generate_preview(geometry, definition) → PreviewSet

[Engine] GeometryEngine
  — curve ops, offset math, connectivity graph, neutral-format round-trip
  — product-blind: operates only on NeutralGeometry + numeric parameters

[Engine] ManufacturingRuleEngine
  resolve(product_type, material, machine) → ResolvedRuleSet
  — implements the resolution order from v2 §13.2, generalized beyond "bridge width"
    to any rule category a ProductDefinition declares

[Engine] GeometryValidationEngine
  run_standard_checks(geometry) → ValidationReport
  — the FR-6 checklist; product-blind; a ProductDefinition selects which checks
    apply and what thresholds via ManufacturingRuleEngine, but the *checks
    themselves* (open curve, self-intersection, etc.) are Core, not per-product

[Engine] ManufacturingAnalysisEngine
  analyze(geometry, resolved_rules, machine, material) → AnalysisResult
  — score/difficulty/risk/time/material-usage math is generic; what counts as
    "successful" for a given product comes from the ProductPlugin's analyze()
    hook, called by this engine, not reimplemented per product

[Engine] AutomaticRepairEngine
  repair(geometry, resolved_rules, similarity_tolerance) → RepairResult

[Engine] ManufacturingKnowledgeEngine
  — owns versioned rule storage/loading (v2's Knowledge Base, generalized;
    see §12)

[Engine] AIRecommendationEngine
  recommend(analysis_result, product_type) → Recommendations
  — rule-based now, model-backed later (v2 §14 reasoning carries over unchanged)

[Engine] MachineEngine
  get_profile(machine_id) → MachineProfile
  recommend_settings(material, machine, product_type) → SettingsRecommendation

[Engine] MaterialEngine
  get_profile(material_id) → MaterialProfile
  — split out of v2's Machine Profile Manager because material properties
    (thickness, hardness, spring-back) are conceptually independent of any
    one machine and are reused across machines — a genericization worth
    making now (🟢 clear win, not speculative)

[Engine] ReportingEngine
  generate(job, template_reference) → Report
  — template-driven, no product-specific report logic in the engine itself

[Engine] PluginEngine
  discover_plugins() → [ProductDefinition + ProductPlugin pairs]
  load(product_type) → (ProductDefinition, ProductPlugin)
  — the Product Definition Loader lives here

[Engine] WorkflowEngine        (§10)
  start(job, workflow_definition) → WorkflowInstance
  advance(instance, event) → WorkflowInstance
  — generic state machine; states/transitions come from WorkflowDefinition,
    which a ProductDefinition references (a product can use the default
    workflow or declare its own)

[Engine] TemplateEngine        (§ Template Engine, 🟡)
  render(template_reference, context) → RenderedArtifact

[Engine] AssetManagementEngine (🟡)
  store(asset) / retrieve(asset_id) / list(filter)

[Engine] QueueManagementEngine (🟡)
  enqueue(job) / status(job_id) / transition(job_id, new_state)

[Engine] NotificationEngine (🟡)
  emit(event) → dispatches to configured channel handlers

[Service group] EnterpriseServices
  Operators, Customers, Licensing, Security, BackupRecovery, QualityInspection
```

---

## 5. Module Diagram (v3)

```
                 ┌────────────────────────────┐
                 │   CAD/UI Adapter (CorelDRAW) │
                 └──────────────┬─────────────┘
                                │ Adapter API
                 ┌──────────────▼─────────────┐
                 │         PMS Core API         │
                 └──────────────┬─────────────┘
                                │
       ┌────────────────────────┼─────────────────────────┐
       │                        │                         │
┌──────▼───────┐       ┌────────▼────────┐       ┌────────▼────────┐
│ Plugin Engine  │──────►│ Product Definition│       │  Workflow Engine   │
│ (discovers &   │       │  (loaded per job) │       │  (per-job state    │
│  loads plugins)│       └────────┬────────┘       │  machine)          │
└──────┬───────┘                 │                 └────────┬────────┘
       │                          │ configures                │
┌──────▼──────────────────────────▼───────────────────────────▼───────┐
│  Geometry Engine │ Validation Engine │ Rule Engine │ Analysis Engine  │
│  Repair Engine   │ Knowledge Engine  │ AI Engine    │ Machine Engine   │
│  Material Engine │ Reporting Engine  │ Template Eng.│ Asset Mgmt Eng.  │
└──────┬───────────────────────────────────────────────────────────────┘
       │
┌──────▼───────────────────────────────────────────────────────────────┐
│  Queue Management │ Notification Engine │ Enterprise Services          │
│  (jobs move through queue states while workflow advances)              │
└────────────────────────────────────────────────────────────────────────┘
       │
┌──────▼───────────────────────────────────────────────────────────────┐
│  Data Layer: Jobs, Customers, Operators, Rule/Material/Machine/         │
│  ProductDefinition versions, WorkflowInstances, Assets                  │
└────────────────────────────────────────────────────────────────────────┘

Products (data, not modules of Core):
  products/emboss_seal/  products/rubber_stamp/  products/_template/
  — each supplies a ProductDefinition + ProductPlugin consumed by Plugin Engine
```

---

## 6. Flowcharts (v3)

### 6.1 Generalized Job Flow (supersedes v2 §6.1 — now workflow-driven, not hardcoded)

```
[Adapter: Import artwork]
        │
        ▼
[Core: Plugin Engine loads ProductDefinition for selected product_type]
        │
        ▼
[Core: Workflow Engine starts WorkflowInstance using ProductDefinition's
        workflow (defaults to platform standard workflow if none declared)]
        │
        ▼
State: "Artwork Imported" ──event──► State: "Manufacturing Analysis"
        │
        ▼
[Analysis Engine + resolved Rule Engine output + ProductPlugin.analyze() hook]
        │
        ▼
State: "Manufacturing Analysis" ──event(score below threshold)──► State: "Automatic Repair"
        │                                                              │
        │event(score acceptable)                                       ▼
        │                                              [Repair Engine + ProductPlugin.repair()]
        │                                                              │
        │◄─────────────────────────re-analyze───────────────────────────┘
        ▼
State: "Preview Generation" ──► [Template Engine renders ProductDefinition's preview template]
        │
        ▼
State: "Customer Approval" ──event(approved)──► State: "Production Ready"
        │event(rejected)
        ▼
back to "Automatic Repair" or "Manufacturing Analysis" per Workflow's declared transition
        │
   (from Production Ready)
        ▼
State: "Laser Processing" ──► [Adapter drives CAD export; Machine/Material Engines
        │                       supply settings; Quality Inspection runs pre-export]
        ▼
State: "Quality Inspection" ──event(PASS)──► State: "Packing"
        │event(FAIL/WARNING)
        ▼
back to appropriate earlier state per Workflow definition
        │
   (from Packing)
        ▼
State: "Delivery" ──► State: "Archive" ──► [Job persisted, WorkflowInstance closed]
```

The critical generalization versus v2: **the sequence of states above is the *default* Workflow Definition PMS ships with, not a hardcoded pipeline.** A different product could declare a workflow that skips "Customer Approval" entirely, or adds a "Second Inspector Sign-off" state — the Workflow Engine doesn't care, as long as the definition is a valid state machine.

### 6.2 Geometry Validation Flow (new — generalizes v2's repair-loop into a standalone reusable checklist)

```
[Geometry Validation Engine.run_standard_checks(geometry)]
        │
        ▼
Run each check independently (order doesn't matter, checks don't depend on each other):
  Open Curves | Duplicate Nodes | Duplicate Objects | Self-Intersections |
  Min Gap | Min Bridge | Min Wall Thickness | Floating Islands | Tiny Holes |
  Node Density | Sharp Angles | Disconnected Objects
        │
        ▼
[Assemble ValidationReport: per-check pass/fail + location + measured value + threshold]
        │
        ▼
Report consumed by:
  - Automatic Repair Engine (decides what to fix)
  - Manufacturing Analysis Engine (feeds into score/risk)
  - Quality Inspection module (pre-export gate)
  - Dashboard UI (human-readable warnings)
```

Making this its own standalone engine (rather than embedded inside Analysis, as v2 had it) is one of the more valuable generalizations in this revision — 🟢 high confidence — because Quality Inspection (a *different* stage of the job, much later, post-repair) needs the exact same checks re-run on the final output geometry, and v2's design would have duplicated that logic.

---

## 7. UI Architecture (v3 — generalized from v2's UI Mockups)

Rather than mock up product-specific screens again (v2 §7 already covers Emboss Seal's dashboard/preview/batch UI reasonably well and doesn't need to be redrawn), v3's contribution is the **UI architecture principle**: every Adapter screen is templated from the active ProductDefinition, not hand-built per product.

- **Dashboard:** renders whatever fields the ProductDefinition's AnalysisResult schema declares (score, difficulty, risk, time, material usage are common to most products but not guaranteed universal — e.g., a future non-laser product might not have "engraving time" at all). The Adapter's dashboard component must therefore be schema-driven, not field-hardcoded. 🟡
- **Preset Picker:** lists whatever presets the loaded ProductDefinition declares — Emboss Seal's nine presets (Pocket/Common/Corporate/etc.) are data, not UI code.
- **Preview Simulator:** renders whichever preview views the ProductDefinition's preview_templates declare (Emboss Seal declares Male/Female/Paper-Impression/Cross-Section; a Rubber Stamp might declare different or additional views like "ink coverage preview").
- **Workflow visualization:** a generic state-machine progress indicator (a horizontal stepper) driven by the active WorkflowInstance — works for any product's workflow without Adapter changes.

This is 🟡 medium confidence specifically because a schema-driven dashboard is more UI engineering effort than a hardcoded one, and it's only worth that cost once a second product (Rubber Stamp) actually needs different fields — worth reassessing once that plugin exists rather than over-building the schema-driven renderer speculatively now.

---

## 8. Plugin Architecture / Product Definition Engine (v3 — the load-bearing section, 🟢)

### 8.1 Why this is the section to get right
Every other engine in this document takes a ProductDefinition (and often a paired ProductPlugin) as input and does generic work. If this contract is wrong, everything downstream inherits the mistake. This is where I'd focus review time if you only have bandwidth to scrutinize one section closely.

### 8.2 What a Product Definition must fully specify (per your list, organized)
1. **Manufacturing Rules** — resolved via the Manufacturing Rule Engine (§ above); a product declares which rule categories it uses and its defaults/overrides.
2. **Validation Rules** — which of the Geometry Validation Engine's standard checks apply, and at what thresholds (a product might legitimately disable "min bridge" if it has no embossing/cutting bridges at all, e.g., a flat name plate).
3. **Repair Rules** — which automatic repairs the product allows, and any product-specific repair hooks via ProductPlugin.repair().
4. **Machine Compatibility** — which Machine Engine profiles/machine types are valid for this product (a Fiber Laser product declares incompatibility with a CO2-only machine profile, etc.).
5. **Material Compatibility** — same idea via Material Engine.
6. **Output Formats** — which export formats are valid/expected (DXF/SVG/CDR/PDF/AI today; a future product might need G-code or a rotary-engraving-specific format).
7. **Layer Structure** — the layer-role taxonomy (Original/Repair/Male/Female/Registration/Cut/Engraving/Target-System, generalizing v2's fixed 8-layer list) — declared per product, since not every product needs a "Male/Female" concept at all.
8. **Production Presets** — data, per §8.2 example below.
9. **Report Templates** — reference into the Template Engine.
10. **Preview Templates** — reference into the Template Engine.
11. **Workflow** — reference into the Workflow Engine, defaulting to the platform standard workflow (§6.1) if unspecified.

### 8.3 ProductPlugin: the behavioral half
Data alone (§8.2) covers configuration; some product logic is genuinely behavioral, not declarative — e.g., "is this specific geometry shape suitable for embossing" involves judgment calls Emboss Seal's plugin code implements, while Rubber Stamp's plugin might weigh the same inputs completely differently. The `ProductPlugin` contract (§4) is where that behavior lives, always called *by* a Core engine, never replacing one.

### 8.4 Plugin registration and isolation
The Plugin Engine discovers Product Definitions + paired plugin code from `products/*/`. Two isolation questions this raises, both flagged rather than casually resolved:
- **In-process vs. sandboxed execution:** internal plugins (Emboss Seal, Rubber Stamp, and any product your own team builds) can reasonably run in-process with Core, trusted the same as Core itself. **Third-party plugins (Extension SDK, §14) cannot be trusted the same way** — running arbitrary third-party code in-process with access to Core's full data layer is a real security exposure (§17). I'm designing the contract now (§4) but deliberately deferring the *execution/sandboxing* model for third-party plugins to §17, since it's a security design problem, not a plugin-contract problem, and conflating them would weaken both.

---

## 9. Manufacturing Core Architecture (v3 — cross-reference index)

This section is intentionally a map rather than new content, since §2–5 already specify each engine — listing here so the deliverable you asked for ("Manufacturing Core Architecture") is easy to navigate:

| Engine | Spec location | Confidence |
|---|---|---|
| Geometry Engine | §4, §6.2 | 🟢 |
| Manufacturing Rule Engine | §4 | 🟢 |
| Geometry Validation Engine | §4, §6.2 | 🟢 |
| Manufacturing Analysis Engine | §4 | 🟢 |
| Automatic Repair Engine | §4 | 🟢 |
| Manufacturing Knowledge Engine | §4, §12 | 🟢 |
| AI Recommendation Engine | §4, §13 | 🟡 |
| Machine Engine | §4 | 🟢 |
| Material Engine | §4 | 🟢 |
| Reporting Engine | §4 | 🟡 |
| Plugin Engine | §4, §8 | 🟢 |
| Workflow Engine | §4, §10 | 🟡 |
| Template Engine | §4, §7 | 🟡 |
| Asset Management Engine | §4, § below | 🔴 |
| Queue Management Engine | §4, § below | 🟡 |
| Notification Engine | §4 | 🟡 |
| Enterprise Services | §4, §14 | 🟡/🔴 mixed |

---

## 10. Workflow Architecture (v3, new detail)

### 10.1 Model
A **finite state machine**: `WorkflowDefinition = {states, transitions, events}`. `WorkflowInstance` is the live, per-job instantiation, persisted so a job's exact position survives a crash/restart (ties to §"Backup & Recovery").

### 10.2 Default workflow
The example sequence you gave (Order Received → Artwork Imported → Manufacturing Analysis → Automatic Repair → Preview Generation → Customer Approval → Production Ready → Laser Processing → Quality Inspection → Packing → Delivery → Archive) ships as the **platform default WorkflowDefinition**, usable as-is by any product that doesn't declare its own.

### 10.3 Per-product overrides
A ProductDefinition may reference a custom WorkflowDefinition (e.g., a product with no customer-approval step, or one requiring a regulatory sign-off state a government-seal variant might need). The Workflow Engine treats the default and any custom definition identically — no special-casing.

### 10.4 Honest limitation
🟡 A generic workflow engine is straightforward for linear-with-branches flows like the example given. If future requirements need parallel states (e.g., "Quality Inspection" and "Packing Prep" happening concurrently), that's a materially more complex state-machine model (parallel/composite states, as in statecharts) — worth flagging now so it's a conscious decision later rather than a surprise when a workflow doesn't fit the simple model.

---

## 11. Geometry Engine Architecture (v3, expanded from v2)

Unchanged in fundamentals from v2 §2.4/§4 (neutral-format geometry, offset math, connectivity graph), with one addition specific to genericization: the Geometry Engine's public surface must not assume "the goal is an embossing die" anywhere — offset generation (v2's "male/female" concept) becomes a generic **parametric offset operation** (`generate_offset_variant(geometry, distance, direction)`), and it's the Emboss Seal ProductPlugin that calls it twice (positive/negative directions) and *labels* the results "Male"/"Female." A different product (e.g., a single-sided Name Plate) simply doesn't call it twice, or at all. 🟢

---

## 12. Manufacturing Knowledge Base Architecture (v3, generalized from v2 §13)

### 12.1 What generalizes cleanly
v2's YAML-based versioned rule storage, resolution order (product → material → default), and "every job records rule-set version" reproducibility guarantee all generalize directly — nothing about that design was embossing-specific. 🟢

### 12.2 What's new: rule categories are now open-ended
v2 hardcoded "bridge/gap/wall/clearance/kerf" as the rule shape. v3's Manufacturing Knowledge Engine stores rules as **named categories a ProductDefinition declares it needs** (still YAML-backed, still versioned), so a future product needing an entirely different rule category (say, "minimum ink channel width" for a Rubber Stamp, or "minimum trace width" for some future electronics-adjacent product) doesn't require a schema change to the Knowledge Engine — only a new category definition. 🟢

### 12.3 Resolution order, generalized
`product_type override → material override → machine override (new — some machines have physical constraints no material-level rule captures, e.g. a specific laser's minimum kerf) → platform default`. 🟢

---

## 13. AI Architecture (v3, minor generalization of v2 §14)

Unchanged in substance: rule-based v1 behind an API shaped for future ML (v2 §14.1), data collection from day one for future training (§14.2). The only genericization needed: `AIRecommendationEngine.recommend()` takes `product_type` and delegates product-specific interpretation to the ProductPlugin where relevant, same pattern as every other engine in this document. 🟢

---

## 14. Enterprise Architecture (v3, expanded)

### 14.1 Carried over from v2, unchanged in scope (Option A, §0.4 of v2, still in force)
Operators, customers, job history, licensing — single-machine/local-shop scope, cloud sync still explicitly deferred (v2 §17 reasoning stands).

### 14.2 New in v3: Security (this is the section your request implicitly requires and didn't explicitly list, so I'm adding it — see §17 for the full treatment)

### 14.3 Backup & Recovery (🟡)
- **Automatic backups:** scheduled snapshots of the data layer (jobs, rule versions, product definitions) and of in-progress job state.
- **Version history:** every RuleSet/ProductDefinition/WorkflowDefinition change is append-only and retrievable (ties directly to §12's versioning).
- **Undo checkpoints:** generalization of v1/v2's per-stage checkpointing, now a Core concept (checkpoint before any destructive engine operation) rather than something the Adapter alone managed.
- **Crash/settings/job recovery:** a WorkflowInstance's persisted state (§10.1) is exactly what makes job recovery possible after a crash — this is a direct benefit of modeling jobs as a state machine rather than an imperative script.

### 14.4 Quality Inspection Module (🟢 — reuses §6.2's Validation Engine directly)
Runs Geometry Validation Engine's standard checks against **final output geometry** (post-repair, post-offset-generation), plus Machine/Material compatibility checks and Target-System export-integrity checks, producing PASS/WARNING/FAIL. Explicitly the same underlying engine as pre-repair validation, run again at a different WorkflowInstance state (§6.1) — not a separate implementation.

### 14.5 Production Queue Manager (🟡)
Queued/Running/Paused/Completed/Failed/Cancelled states, tracked independently of WorkflowInstance state (a job can be "Queued" in the manufacturing sense while its Workflow is sitting at "Customer Approval" — these are two different state machines answering different questions: *is a human/machine actively working this job right now* vs. *where is this job in its overall lifecycle*). Worth being precise about that distinction now, since conflating Queue state and Workflow state was a plausible design mistake I actively avoided here.

---

## 15. Scalability Strategy (v3, updated from v2 §15a)

Unchanged reasoning from v2 (SQLite at single-shop scale, REST API boundary enables later cloud extraction), with one addition: **Product Definitions and plugins scale independently of Core** — adding product #10 doesn't grow Core's engine count, only `products/`'s content, which was the entire point of §2.2's strict no-product-branching rule. This is meaningfully stronger than v2's plugin scalability claim (v2 §15a), because v2 still had some product-shaped naming in Core; v3 doesn't.

---

## 16. Performance Strategy (v3, updated from v2 §15b)

Carries over v2's reasoning (localhost latency negligible, geometry hot-paths isolated for later optimization, Adapter/CAD automation is the batch-throughput bottleneck, not Core) with one new consideration: **the Workflow Engine's state persistence must not become a per-transition performance tax** — if every state transition triggers a full job-record write, high-volume batch processing (hundreds of jobs/day across future multi-operator scale) could bottleneck on the data layer rather than on CorelDRAW automation as originally assumed. Recommend write-batching or async persistence for workflow transitions once real throughput numbers exist — flagged as a **watch item**, not a current problem, since current volume doesn't justify solving it preemptively. 🟡

---

## 17. Security Strategy (new section — you didn't explicitly ask for this by name but the Extension SDK requirement implies it, so I'm treating it as required)

### 17.1 Why this is now unavoidable
v1 and v2 had no meaningful external attack surface — a single-user CorelDRAW macro. v3 introduces: (a) a long-running local service (Core) with a network-facing API, even if localhost-only initially, (b) an Extension SDK inviting **third-party code** to run against that service, and (c) enterprise data (customer records, job history) worth protecting. Each of these needs an explicit answer, not an assumption.

### 17.2 Local API surface
Even "localhost-only" is not automatically safe — any process on the machine can currently call a bare localhost HTTP API. Recommend: a local auth token (generated at Core startup, shared only with authorized Adapters) required on every request, and binding strictly to `127.0.0.1` (never `0.0.0.0`) unless/until §17 of v2 (cloud phase) is actually built with proper network security design. 🟢 — this is a small, cheap thing to get right now rather than retrofit.

### 17.3 Third-party plugin trust boundary (the Extension SDK's core problem)
Recommend a staged trust model rather than treating "plugin" as one uniform category:
- **Tier 1 — Internal plugins** (Emboss Seal, Rubber Stamp, anything your team builds): run in-process, full trust, same as Core.
- **Tier 2 — Reviewed third-party plugins:** code-reviewed by you/your team before distribution, still run in-process but with a defined, audited surface (they only get access to the Extension SDK's documented APIs, not raw data-layer access).
- **Tier 3 — Unreviewed/marketplace-style third-party plugins:** would need actual process isolation (separate OS process, restricted filesystem/network access, resource limits) — this is a substantially bigger engineering investment (sandboxing infrastructure) than tiers 1–2, and I'd defer building Tier 3 support until there's real demand for an open plugin marketplace, rather than building sandbox infrastructure speculatively now. 🔴 flagged as explicitly out of scope for the current roadmap.

### 17.4 Data protection
Customer records and job history (§14.1) warrant at-rest encryption of the SQLite file (or equivalent) and access control tied to Operator accounts (§14.1) — straightforward at single-shop scale, revisit properly if/when the cloud phase (v2 §17) introduces multi-tenant storage.

### 17.5 Rule/definition tampering
Because reproducibility (§12) depends on rule/definition versions being trustworthy, version records should be **append-only and checksummed** so a corrupted or maliciously edited historical rule version is detectable, not silently trusted — relevant for any future warranty/dispute scenario as much as for security per se.

### 17.6 Licensing integrity
Deferred to implementation-phase detail (this is a business-logic-plus-security topic, not pure architecture), but flagging now that licensing (§14.1, FR from v1 §15) and plugin trust (§17.3) interact — a licensing scheme should account for which plugin tier is active, since Tier 3 (if ever built) changes the platform's risk profile in ways that might reasonably affect licensing terms.

---

## 18. Testing Strategy (v3, additions over v2 §9)

- **Product Definition conformance suite:** generalizes v2's plugin conformance suite (v2 §9) — validates that any ProductDefinition + ProductPlugin pair satisfies the full contract (§8.2/§4) before being allowed to register, including edge cases like "declares zero validation rules" or "declares a custom workflow with an unreachable state."
- **Cross-plugin regression:** once Rubber Stamp exists, a regression suite runs both plugins against every Core engine change, specifically to catch the "worked for Emboss Seal, silently broke Rubber Stamp" class of bug that's the whole risk named in §0.2.
- **Workflow state-machine tests:** every declared transition in both the default and any custom WorkflowDefinition must be reachable and every state must have a defined exit path (no dead-end states) — a structural validation, not just a functional test.
- **Security tests:** localhost API rejects unauthenticated requests (§17.2); Tier 2 plugin sandboxing (§17.3) is tested against its documented API surface, confirming it cannot reach undocumented Core internals.
- Everything from v2 §9 (determinism, contract tests, neutral-format round-trip) carries over unchanged and remains equally important.

---

## 19. Risk Analysis (v3, additions/updates over v2 §11)

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Over-generalized abstractions (§0.2) prove wrong once Rubber Stamp is built, requiring Core rework | **High** | Medium | Explicitly budget rework time after Rubber Stamp ships (§0.2); don't treat this document's engine boundaries as frozen until then |
| Workflow Engine's simple state-machine model doesn't fit a future parallel-states requirement (§10.4) | Medium | Medium | Documented limitation now; revisit if/when a real product needs concurrent states |
| Extension SDK (Tier 3, §17.3) gets built before there's real third-party demand, wasting sandboxing investment | Medium | Medium | Explicitly deferred; build Tier 1/2 only until demand is proven |
| Schema-driven, product-agnostic UI (§7) costs more engineering time than it returns if only 2–3 products ever exist | Medium | Low–Medium | Reassess after Rubber Stamp; a semi-hardcoded UI with a few conditional fields might be pragmatically better than a fully generic renderer at small scale |
| Local API without proper auth (§17.2) gets skipped as "we'll add it later" and becomes a real exposure once more processes run on shop-floor machines | Low–Medium | Medium | Cheap enough to build now (§17.2); don't defer |
| All prior v1/v2 risks (PowerTRACE quirks, geometry round-trip fidelity, VBA↔HTTP viability) | Unchanged | Unchanged | Carried forward, still unresolved until the relevant implementation spikes happen |

---

## 20. Migration Strategy (new)

### 20.1 From v2's design to v3's, conceptually
Nothing has been built yet, so there's no code migration — but worth stating the mapping so the intent is traceable: v2's `EmbossSealPro.Core` becomes `PMS core/` (product-blind engines) **plus** `products/emboss_seal/` (everything that was actually embossing-specific inside v2's engines moves here). v2's `CorelDrawConnector` becomes `adapters/coreldraw/` with no functional change.

### 20.2 Rule-set and API versioning discipline
Both carried over from v2 (§10 coding standards, API version discipline) and now additionally apply to ProductDefinition versions and WorkflowDefinition versions — same discipline, more version axes to track (§7's job-record versioning, generalized from v2 §12.3/13.1).

### 20.3 Adapter-language migration path (the "C#/Python/C++" requirement from your original brief)
Unchanged reasoning from v2 §0.2/§2: because the Adapter only ever talks to Core through the versioned API (§2.1), replacing CorelDRAW VBA with a different CAD adapter in a different language is a matter of implementing the same Adapter contract in that language — Core doesn't change. This remains the central payoff of the whole Core/Adapter decision and nothing in v3 weakens it.

### 20.4 Third product onward
`docs/ProductDefinitionAuthoringGuide.md` (§3 folder structure) is the intended artifact that makes adding product #3+ a documented process rather than tribal knowledge — worth writing this guide immediately after Rubber Stamp ships, while its lessons are fresh.

---

## 21. Future Expansion Roadmap (new — the 10–15 year view)

This is explicitly a **directional roadmap, not a committed plan** — the near-term roadmap (v2 §8's 17 phases, now reframed around Core+Emboss Seal+Rubber Stamp) is still the actual plan to execute. This section answers "does the architecture leave room," not "when will we build it."

| Horizon | Plausible expansion | Architectural readiness |
|---|---|---|
| **Near (post Rubber Stamp)** | Flash Stamp, Wax Seal, Corporate/Common/Library Seal (likely thin variants of Emboss Seal's ProductDefinition rather than new plugins) | Ready now — this is exactly what §8 is for |
| **Near–Mid** | Name Plates (single-sided, no Male/Female concept — good stress test of §11's "offset is optional" design) | Ready now |
| **Mid** | Rotary Engraving, Coin Dies, Leather Stamps (different physical processes, likely new rule categories per §12.2 and possibly new Machine Engine profile types) | Architecture supports it; Machine Engine's profile schema will likely need extension (flagged, not a redesign) |
| **Mid–Far** | Fiber Laser, UV Laser (different machine physics entirely — may need machine-type-specific settings recommendation logic beyond what Machine Engine currently models) | Needs a dedicated look when reached, per v2 §12.3's original flag — still true |
| **Far** | Cloud/multi-shop (v2 §17), open third-party Extension SDK Tier 3 (§17.3), parallel workflow states (§10.4) | Explicitly deferred, architecturally reachable without redesign per §20.3's reasoning, but each is its own project |

---

## Summary — What's Actually Ready to Build, and What I'd Still Push Back On

**Ready:** §8 (Product Definition/Plugin contract), §4/§9 (Core engines it's built on), §12 (Knowledge Base), §11 (Geometry Engine), §17.2 (basic local API auth) — these are 🟢 and I'd start here.

**Build, but expect to revise once Rubber Stamp exists:** §10 (Workflow Engine), §7 (schema-driven UI), §14.5 (Queue Manager), §14.3 (Backup/Recovery) — all 🟡, all reasonable first drafts.

**I'd genuinely defer, not just build a stub for:** the Extension SDK's Tier 3 sandboxing (§17.3) and the full Template/Asset Management engines' cross-product generality (§ Template Engine, § Asset Management) — 🔴, speculative enough that building them now risks solving problems you don't have yet at the expense of problems you do (shipping Emboss Seal and Rubber Stamp as real, working plugins).

Tell me if you want me to proceed exactly as specified across the board, or to formally descope the 🔴 items from the near-term roadmap while keeping their contracts documented here for later. Once you confirm, I'll hold here — no implementation, per your instruction — until you say to begin.
