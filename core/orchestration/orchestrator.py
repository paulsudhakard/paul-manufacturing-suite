"""Pipeline Orchestrator.

Coordinates the existing, already-implemented engines in this fixed
order:

    1. SVG Import              core.engines.geometry.io.svg_io
    2. Geometry Validation     core.engines.geometry.validation
    3. Geometry Repair         core.engines.geometry.repair
    4. Manufacturing Validation core.engines.manufacturing.validator
    5. Manufacturing Repair    core.engines.manufacturing.repair
    6. Male Generator          core.engines.manufacturing.male_female
    7. Female Generator        core.engines.manufacturing.male_female
    8. Preview Generator       core.engines.manufacturing.preview
    9. DXF Export              core.engines.geometry.io.dxf_io +
                                core.engines.manufacturing.rdworks_layers
    10. Validation Report      (see note below)

This module contains no geometry, manufacturing, or file-format logic
of its own -- every step is a direct call into an existing, unmodified
function. The only "work" done here is sequencing calls and carrying
each step's output into the next, plus assembling step 10's report from
data already produced by steps 2-5 (see the docstring on `_build_validation_report`).

Note on step 10 (Validation Report): no dedicated report-generation
module exists in the repository (confirmed by repository audit -- see
docs). Rather than write a new report-formatting algorithm, step 10
here is pure data aggregation: it packages the `GeometryIssue` and
`ManufacturingWarning` lists and repair actions already produced by
steps 2-5 into a plain, JSON-serializable structure. No new validation
logic is introduced.

See docs/ORCHESTRATOR_SEQUENCE.md for the sequence diagram.
"""
from __future__ import annotations

from dataclasses import dataclass

from core.engines.geometry.bounds import bounding_box
from core.engines.geometry.io.dxf_io import build_dxf
from core.engines.geometry.io.neutral_io import neutral_to_shape
from core.engines.geometry.io.svg_io import svg_to_neutral
from core.engines.geometry.model import CompoundPath
from core.engines.geometry.repair import repair_geometry
from core.engines.geometry.validation import GeometryIssue
from core.engines.geometry.validation import validate_geometry as validate_geometry_structural
from core.engines.manufacturing.male_female import (
    MaleFemaleResult,
    generate_female,
    generate_male,
    generate_relief,
    registration_marks,
    alignment_marks,
)
from core.engines.manufacturing.preview import ManufacturingPreview, generate_preview
from core.engines.manufacturing.rdworks_layers import preview_to_dxf_layers
from core.engines.manufacturing.repair import ManufacturingRepairResult, repair_manufacturing
from core.engines.manufacturing.rules import RuleSet
from core.engines.manufacturing.validator import ManufacturingWarning, validate_manufacturing


@dataclass(frozen=True)
class OrchestratorResult:
    """Everything each stage produced, kept independently inspectable --
    same pattern as the existing `core.engines.manufacturing.pipeline
    .PipelineResult`, extended with the SVG-import stage and the
    validation-report aggregation.
    """

    original: CompoundPath
    geometry_issues_before: tuple[GeometryIssue, ...]
    geometry_repair_actions: tuple[str, ...]
    repaired: CompoundPath
    manufacturing_warnings_before: tuple[ManufacturingWarning, ...]
    manufacturing_repair: ManufacturingRepairResult
    manufacturing_warnings_after: tuple[ManufacturingWarning, ...]
    male_female: MaleFemaleResult
    preview: ManufacturingPreview
    dxf_text: str
    validation_report: dict


def _build_validation_report(result_so_far: dict) -> dict:
    """Pure aggregation of data already produced by steps 2-5 -- no new
    checks are run here. `result_so_far` holds the intermediate values
    collected while `run()` executes; this function only reshapes them
    into a JSON-serializable dict.
    """

    def issue_to_dict(issue: GeometryIssue) -> dict:
        return {
            "issue_type": issue.issue_type.value,
            "path_index": issue.path_index,
            "segment_index": issue.segment_index,
            "detail": issue.detail,
        }

    def warning_to_dict(warning: ManufacturingWarning) -> dict:
        return {
            "warning_type": warning.warning_type.value,
            "subpath_index": warning.subpath_index,
            "related_subpath_index": warning.related_subpath_index,
            "measured_value": warning.measured_value,
            "threshold_value": warning.threshold_value,
            "detail": warning.detail,
        }

    return {
        "geometry_issues_before": [
            issue_to_dict(i) for i in result_so_far["geometry_issues_before"]
        ],
        "geometry_repair_actions": list(result_so_far["geometry_repair_actions"]),
        "manufacturing_warnings_before": [
            warning_to_dict(w) for w in result_so_far["manufacturing_warnings_before"]
        ],
        "manufacturing_repair_actions": list(result_so_far["manufacturing_repair"].actions),
        "manufacturing_repair_similarity": result_so_far["manufacturing_repair"].similarity,
        "manufacturing_warnings_after": [
            warning_to_dict(w) for w in result_so_far["manufacturing_warnings_after"]
        ],
        "passed": len(result_so_far["manufacturing_warnings_after"]) == 0,
    }


def run(
    svg_text: str,
    rule_set: RuleSet | None = None,
    source_file_hint: str | None = None,
    on_progress=None,
) -> OrchestratorResult:
    """Runs the full 10-step pipeline against SVG text. `on_progress`,
    if given, is called with a short label string before each stage --
    the CLI uses this to print progress lines; the orchestrator itself
    has no notion of "display."
    """

    def report(stage: str) -> None:
        if on_progress is not None:
            on_progress(stage)

    rule_set = rule_set or RuleSet.load_default()

    # 1. SVG Import
    report("svg_import")
    neutral = svg_to_neutral(svg_text, source_file_hint=source_file_hint)
    original = neutral_to_shape(neutral)

    # 2. Geometry Validation
    report("geometry_validation")
    geometry_issues_before = tuple(
        validate_geometry_structural(original, rule_set.flatten_tolerance_mm)
    )

    # 3. Geometry Repair
    report("geometry_repair")
    geometry_repaired, geometry_repair_actions = repair_geometry(original)

    # 4. Manufacturing Validation
    report("manufacturing_validation")
    manufacturing_warnings_before = tuple(validate_manufacturing(geometry_repaired, rule_set))

    # 5. Manufacturing Repair
    report("manufacturing_repair")
    manufacturing_repair = repair_manufacturing(geometry_repaired, rule_set)
    repaired = manufacturing_repair.compound
    manufacturing_warnings_after = tuple(validate_manufacturing(repaired, rule_set))

    # 6. Male Generator
    report("male_generator")
    male = generate_male(repaired, rule_set)

    # 7. Female Generator
    report("female_generator")
    female = generate_female(repaired, rule_set)

    bbox = bounding_box(repaired)
    male_female = MaleFemaleResult(
        male=male,
        female=female,
        registration=registration_marks(bbox, rule_set),
        alignment=alignment_marks(bbox, rule_set),
        relief=generate_relief(repaired, rule_set),
    )

    # 8. Preview Generator
    report("preview_generator")
    preview = generate_preview(original, repaired, male_female, rule_set)

    # 9. DXF Export
    report("dxf_export")
    dxf_text = build_dxf(preview_to_dxf_layers(preview), tolerance=rule_set.flatten_tolerance_mm)

    # 10. Validation Report
    report("validation_report")
    intermediate = {
        "geometry_issues_before": geometry_issues_before,
        "geometry_repair_actions": geometry_repair_actions,
        "manufacturing_warnings_before": manufacturing_warnings_before,
        "manufacturing_repair": manufacturing_repair,
        "manufacturing_warnings_after": manufacturing_warnings_after,
    }
    validation_report = _build_validation_report(intermediate)

    return OrchestratorResult(
        original=original,
        geometry_issues_before=geometry_issues_before,
        geometry_repair_actions=geometry_repair_actions,
        repaired=repaired,
        manufacturing_warnings_before=manufacturing_warnings_before,
        manufacturing_repair=manufacturing_repair,
        manufacturing_warnings_after=manufacturing_warnings_after,
        male_female=male_female,
        preview=preview,
        dxf_text=dxf_text,
        validation_report=validation_report,
    )
