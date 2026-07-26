# Orchestrator Sequence Diagram

Shows `core.orchestration.orchestrator.run()` coordinating existing,
unmodified modules in the required order. The orchestrator itself
performs no geometry/manufacturing computation — every box below is an
existing function; the orchestrator only sequences the calls and
passes each step's output into the next.

```mermaid
sequenceDiagram
    participant Caller
    participant Orchestrator as orchestrator.run()
    participant SVG as svg_io
    participant NeutralIO as neutral_io
    participant GeomValid as geometry.validation
    participant GeomRepair as geometry.repair
    participant MfgValid as manufacturing.validator
    participant MfgRepair as manufacturing.repair
    participant MaleFemale as manufacturing.male_female
    participant Preview as manufacturing.preview
    participant DXF as dxf_io + rdworks_layers

    Caller->>Orchestrator: run(svg_text, rule_set)

    Note over Orchestrator,SVG: 1. SVG Import
    Orchestrator->>SVG: svg_to_neutral(svg_text)
    SVG-->>Orchestrator: NeutralGeometry
    Orchestrator->>NeutralIO: neutral_to_shape(geometry)
    NeutralIO-->>Orchestrator: CompoundPath (original)

    Note over Orchestrator,GeomValid: 2. Geometry Validation
    Orchestrator->>GeomValid: validate_geometry(original)
    GeomValid-->>Orchestrator: GeometryIssue[] (before)

    Note over Orchestrator,GeomRepair: 3. Geometry Repair
    Orchestrator->>GeomRepair: repair_geometry(original)
    GeomRepair-->>Orchestrator: CompoundPath (repaired), actions

    Note over Orchestrator,MfgValid: 4. Manufacturing Validation
    Orchestrator->>MfgValid: validate_manufacturing(repaired, rule_set)
    MfgValid-->>Orchestrator: ManufacturingWarning[] (before)

    Note over Orchestrator,MfgRepair: 5. Manufacturing Repair
    Orchestrator->>MfgRepair: repair_manufacturing(repaired, rule_set)
    MfgRepair-->>Orchestrator: ManufacturingRepairResult
    Orchestrator->>MfgValid: validate_manufacturing(result.compound, rule_set)
    MfgValid-->>Orchestrator: ManufacturingWarning[] (after)

    Note over Orchestrator,MaleFemale: 6. Male Generator
    Orchestrator->>MaleFemale: generate_male(compound, rule_set)
    MaleFemale-->>Orchestrator: CompoundPath (male)

    Note over Orchestrator,MaleFemale: 7. Female Generator
    Orchestrator->>MaleFemale: generate_female(compound, rule_set)
    MaleFemale-->>Orchestrator: CompoundPath (female)

    Note over Orchestrator,Preview: 8. Preview Generator
    Orchestrator->>Preview: generate_preview(original, repaired, male_female, rule_set)
    Preview-->>Orchestrator: ManufacturingPreview

    Note over Orchestrator,DXF: 9. DXF Export
    Orchestrator->>DXF: build_dxf(preview_to_dxf_layers(preview))
    DXF-->>Orchestrator: DXF text

    Note over Orchestrator: 10. Validation Report<br/>(data aggregation only -<br/>no new module, see below)
    Orchestrator->>Orchestrator: assemble report from<br/>steps 2, 3, 4, 5 outputs

    Orchestrator-->>Caller: OrchestratorResult
```

## Notes

- **Steps 1–9** each call one existing, unmodified module. No new
  geometry, manufacturing, or file-format algorithm was written to
  build the orchestrator itself.
- **Step 10** ("Validation Report") has no dedicated module in the
  repository (confirmed missing by the prior repository audit). Rather
  than write a new report-generation algorithm, the orchestrator
  reshapes data already produced by steps 2–5
  (`GeometryIssue` list, `ManufacturingWarning` lists, repair actions,
  similarity score) into a plain JSON-serializable `dict`. This is data
  aggregation, not new validation logic.
- Manufacturing Validation (step 4) is deliberately run a second time
  after Manufacturing Repair (step 5), against the *repaired* geometry
  — this reuses the exact same `validate_manufacturing()` call both
  times, matching the "before/after" pattern already used by the
  existing `core.engines.manufacturing.pipeline.run_pipeline()`.
- Male (6) and Female (7) generation are called as two separate steps,
  matching the audit's finding that `generate_male()` and
  `generate_female()` already exist as independent functions — the
  orchestrator does not use the existing `generate_male_female()`
  convenience wrapper, so that the sequence diagram's step 6/step 7
  distinction is real in the code, not just in the diagram.
