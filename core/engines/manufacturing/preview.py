"""Manufacturing Preview Generator. Produces a structured bundle of
geometry (Original, Repaired, Male, Female) plus lightweight difference
metrics between stages — data only, no visual rendering (the Template/
Rendering Engine is out of scope; a future UI or the Visualizer can
render this bundle).
"""
from __future__ import annotations

from dataclasses import dataclass

from core.engines.geometry.measure import area as compute_area
from core.engines.geometry.measure import perimeter as compute_perimeter
from core.engines.geometry.model import CompoundPath, Shape, as_compound
from core.engines.manufacturing.male_female import MaleFemaleResult
from core.engines.manufacturing.rules import RuleSet


@dataclass(frozen=True)
class DiffSummary:
    """Coarse, geometry-level difference between two stages — not a
    pixel/visual diff (no rendering exists), but enough to say "how much
    changed" numerically and flag which subpath count changed.
    """

    area_before: float
    area_after: float
    area_delta: float
    perimeter_before: float
    perimeter_after: float
    perimeter_delta: float
    subpath_count_before: int
    subpath_count_after: int


def diff_summary(before: Shape, after: Shape, tolerance: float) -> DiffSummary:
    before_c, after_c = as_compound(before), as_compound(after)
    area_before = compute_area(before_c, tolerance)
    area_after = compute_area(after_c, tolerance)
    perim_before = compute_perimeter(before_c, tolerance)
    perim_after = compute_perimeter(after_c, tolerance)
    return DiffSummary(
        area_before=area_before,
        area_after=area_after,
        area_delta=area_after - area_before,
        perimeter_before=perim_before,
        perimeter_after=perim_after,
        perimeter_delta=perim_after - perim_before,
        subpath_count_before=len(before_c.paths),
        subpath_count_after=len(after_c.paths),
    )


@dataclass(frozen=True)
class ManufacturingPreview:
    original: CompoundPath
    repaired: CompoundPath
    male: CompoundPath
    female: CompoundPath
    registration: tuple
    alignment: tuple
    relief: CompoundPath
    original_vs_repaired: DiffSummary
    repaired_vs_male: DiffSummary
    repaired_vs_female: DiffSummary


def generate_preview(
    original: Shape,
    repaired: Shape,
    male_female: MaleFemaleResult,
    rule_set: RuleSet,
) -> ManufacturingPreview:
    tol = rule_set.flatten_tolerance_mm
    return ManufacturingPreview(
        original=as_compound(original),
        repaired=as_compound(repaired),
        male=male_female.male,
        female=male_female.female,
        registration=male_female.registration,
        alignment=male_female.alignment,
        relief=male_female.relief,
        original_vs_repaired=diff_summary(original, repaired, tol),
        repaired_vs_male=diff_summary(repaired, male_female.male, tol),
        repaired_vs_female=diff_summary(repaired, male_female.female, tol),
    )
