"""End-to-end Manufacturing Pipeline: Import -> Analyse -> Validate ->
Repair -> Generate Male -> Generate Female -> Compare with Original ->
Produce DXF. `run_pipeline` is the single entry point a real logo goes
through once supplied; every stage's output is retained on
`PipelineResult` for independent inspection.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.engines.geometry.io.dxf_io import build_dxf
from core.engines.geometry.model import CompoundPath, Shape, as_compound
from core.engines.geometry.validation import GeometryIssue
from core.engines.geometry.validation import validate_geometry as validate_structural
from core.engines.manufacturing.male_female import MaleFemaleResult, generate_male_female
from core.engines.manufacturing.preview import ManufacturingPreview, generate_preview
from core.engines.manufacturing.rdworks_layers import preview_to_dxf_layers
from core.engines.manufacturing.repair import ManufacturingRepairResult, repair_manufacturing
from core.engines.manufacturing.rules import RuleSet
from core.engines.manufacturing.validator import ManufacturingWarning, validate_manufacturing


@dataclass(frozen=True)
class PipelineResult:
    original: CompoundPath
    structural_issues_before: tuple[GeometryIssue, ...]
    manufacturing_warnings_before: tuple[ManufacturingWarning, ...]
    repair: ManufacturingRepairResult
    structural_issues_after: tuple[GeometryIssue, ...]
    manufacturing_warnings_after: tuple[ManufacturingWarning, ...]
    male_female: MaleFemaleResult
    preview: ManufacturingPreview
    dxf_text: str


def run_pipeline(shape: Shape, rule_set: RuleSet | None = None) -> PipelineResult:
    rule_set = rule_set or RuleSet.load_default()
    original = as_compound(shape)

    structural_before = tuple(validate_structural(original, rule_set.flatten_tolerance_mm))
    warnings_before = tuple(validate_manufacturing(original, rule_set))

    repair_result = repair_manufacturing(original, rule_set)

    structural_after = tuple(
        validate_structural(repair_result.compound, rule_set.flatten_tolerance_mm)
    )
    warnings_after = tuple(validate_manufacturing(repair_result.compound, rule_set))

    male_female = generate_male_female(repair_result.compound, rule_set)
    preview = generate_preview(original, repair_result.compound, male_female, rule_set)

    dxf_text = build_dxf(preview_to_dxf_layers(preview), tolerance=rule_set.flatten_tolerance_mm)

    return PipelineResult(
        original=original,
        structural_issues_before=structural_before,
        manufacturing_warnings_before=warnings_before,
        repair=repair_result,
        structural_issues_after=structural_after,
        manufacturing_warnings_after=warnings_after,
        male_female=male_female,
        preview=preview,
        dxf_text=dxf_text,
    )
