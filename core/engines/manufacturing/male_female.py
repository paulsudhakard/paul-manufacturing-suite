"""Male/Female Die Generator (Architecture v3 §11's `generate_offset_variant`,
called twice with opposite directions — this module is the manufacturing-
specific caller that labels and configures those two calls). Output is
geometry only — no DXF/layer concerns here (that's dxf_io.py + rdworks_layers.py).

Clearance formula (first-draft, engineering judgment — same status as
every other unvalidated constant in this project; needs real laser/
material testing before being trusted as final):

    male_offset   = +(clearance/2 + kerf_compensation/2) - paper_deformation_allowance
    female_offset = -(clearance/2 + kerf_compensation/2 + material_compensation)

Rationale: clearance is split evenly so male and female each move half
the total gap; kerf_compensation corrects for the laser beam's own
width on both dies; paper_deformation_allowance only applies to the
male (it's the die that presses into paper and deforms it locally);
material_compensation only applies to the female (it accounts for the
die material's own tolerance).
"""
from __future__ import annotations

from dataclasses import dataclass

from core.engines.geometry.bounds import BoundingBox, bounding_box
from core.engines.geometry.model import (
    Circle,
    CompoundPath,
    Point,
    Polygon,
    Shape,
    as_compound,
)
from core.engines.geometry.offset import JoinStyle, offset_shape
from core.engines.manufacturing.rules import RuleSet


def male_offset_distance(rule_set: RuleSet) -> float:
    return (rule_set.clearance_mm / 2 + rule_set.kerf_compensation_mm / 2) - (
        rule_set.paper_deformation_allowance_mm
    )


def female_offset_distance(rule_set: RuleSet) -> float:
    return -(
        rule_set.clearance_mm / 2
        + rule_set.kerf_compensation_mm / 2
        + rule_set.material_compensation_mm
    )


def generate_male(shape: Shape, rule_set: RuleSet) -> CompoundPath:
    distance = male_offset_distance(rule_set)
    if distance == 0:
        return as_compound(shape)
    paths = offset_shape(shape, distance, JoinStyle.ROUND, tolerance=rule_set.flatten_tolerance_mm)
    return CompoundPath(paths)


def generate_female(shape: Shape, rule_set: RuleSet) -> CompoundPath:
    distance = female_offset_distance(rule_set)
    if distance == 0:
        return as_compound(shape)
    paths = offset_shape(shape, distance, JoinStyle.ROUND, tolerance=rule_set.flatten_tolerance_mm)
    return CompoundPath(paths)


# --- Relief -----------------------------------------------------------------


def generate_relief(shape: Shape, rule_set: RuleSet) -> CompoundPath:
    """A relief zone: an outward offset boundary by `relief_depth_mm`,
    marking the area that should be recessed/cleared around fine detail
    so it isn't crushed during embossing. Output is the offset boundary
    itself (a "relief outline"), not a filled/computed relief volume —
    volumetric relief modeling is a manufacturing-process detail beyond
    this engine's 2D-geometry scope.
    """
    paths = offset_shape(
        shape, rule_set.relief_depth_mm, JoinStyle.ROUND, tolerance=rule_set.flatten_tolerance_mm
    )
    return CompoundPath(paths)


# --- Registration / alignment marks -----------------------------------------


def registration_marks(bbox: BoundingBox, rule_set: RuleSet) -> tuple[Shape, ...]:
    """Two small circles at diagonally opposite corners outside the
    bounding box — used to align Male and Female dies during production.
    """
    r = rule_set.registration_mark_diameter_mm / 2
    margin = rule_set.registration_mark_margin_mm
    return (
        Circle(Point(bbox.min_x - margin, bbox.min_y - margin), r),
        Circle(Point(bbox.max_x + margin, bbox.max_y + margin), r),
    )


def alignment_marks(bbox: BoundingBox, rule_set: RuleSet) -> tuple[Shape, ...]:
    """A third marker, a small triangle at the top-center margin,
    deliberately asymmetric relative to the two registration circles so
    the die's rotation is unambiguous even if someone tries to align
    using only symmetric registration marks.
    """
    size = rule_set.alignment_mark_size_mm
    margin = rule_set.alignment_mark_margin_mm
    cx = (bbox.min_x + bbox.max_x) / 2
    top_y = bbox.max_y + margin
    triangle = Polygon(
        (
            Point(cx, top_y + size),
            Point(cx - size / 2, top_y),
            Point(cx + size / 2, top_y),
        )
    )
    return (triangle,)


@dataclass(frozen=True)
class MaleFemaleResult:
    male: CompoundPath
    female: CompoundPath
    registration: tuple[Shape, ...]
    alignment: tuple[Shape, ...]
    relief: CompoundPath


def generate_male_female(shape: Shape, rule_set: RuleSet) -> MaleFemaleResult:
    bbox = bounding_box(shape)
    return MaleFemaleResult(
        male=generate_male(shape, rule_set),
        female=generate_female(shape, rule_set),
        registration=registration_marks(bbox, rule_set),
        alignment=alignment_marks(bbox, rule_set),
        relief=generate_relief(shape, rule_set),
    )
