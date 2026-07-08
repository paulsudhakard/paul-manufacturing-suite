# core/engines/validation/

The eleven standard geometry defect checks (open curves, duplicate
nodes/objects, self-intersections, min gap/bridge/wall, floating islands,
tiny holes, node density, sharp angles, disconnected objects) plus the
`ValidationReport` assembler (FR-6, Architecture v3 §6.2).

**Arrives:** Sprint 6. Reused unchanged for Quality Inspection in Sprint 17
(same code path, not a reimplementation — Architecture v3 §14.4).
