"""Boolean *preparation* — deliberately not full union/intersection/
difference algorithms. Real polygon boolean ops (Weiler-Atherton,
Vatti, Greiner-Hormann...) require robust handling of degenerate cases
(shared edges, tangencies, numerical edge cases in polygon
reconstruction) that's a substantial project on its own and easy to get
subtly wrong. What a real boolean engine needs as *input* is exactly
what this module provides:

  1. every intersection point between two shapes' edges
     (`find_intersections`)
  2. for each subpath, which points are inside/outside the other shape
     (`classify_subpath`)

`prepare_boolean` bundles both for a given pair of shapes and an
operation kind, so a future full boolean engine has a well-defined
input contract to build on without re-deriving intersection math.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.engines.geometry.flatten import DEFAULT_TOLERANCE_MM, flatten_compound
from core.engines.geometry.model import Point, Shape, as_compound
from core.engines.geometry.winding import FillRule, point_in_compound


class BooleanKind(Enum):
    UNION = "union"
    INTERSECTION = "intersection"
    DIFFERENCE = "difference"


@dataclass(frozen=True)
class Intersection:
    point: Point
    subject_edge_index: int  # index into the flattened subject polygon's edges
    clip_edge_index: int


def _segment_intersection(p1: Point, p2: Point, p3: Point, p4: Point) -> Point | None:
    x1, y1, x2, y2 = p1.x, p1.y, p2.x, p2.y
    x3, y3, x4, y4 = p3.x, p3.y, p4.x, p4.y
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-12:
        return None  # parallel or collinear — not reported as a crossing point
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = ((x1 - x3) * (y1 - y2) - (y1 - y3) * (x1 - x2)) / denom
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return Point(x1 + t * (x2 - x1), y1 + t * (y2 - y1))
    return None


def find_intersections(
    subject: tuple[Point, ...], clip: tuple[Point, ...]
) -> tuple[Intersection, ...]:
    """All intersection points between two closed point rings' edges.
    O(n*m) — correctness over speed, per this engine's stated priority;
    fine at manufacturing-artwork scale (hundreds, not millions, of
    edges).
    """
    n, m = len(subject), len(clip)
    results = []
    for i in range(n):
        a1, a2 = subject[i], subject[(i + 1) % n]
        for j in range(m):
            b1, b2 = clip[j], clip[(j + 1) % m]
            point = _segment_intersection(a1, a2, b1, b2)
            if point is not None:
                results.append(Intersection(point, i, j))
    return tuple(results)


class PointClass(Enum):
    INSIDE = "inside"
    OUTSIDE = "outside"
    ON_BOUNDARY = "on_boundary"  # not distinguished from OUTSIDE by the
    # winding/crossing tests below (boundary is a measure-zero case);
    # reserved for a future exact predicate if a consumer needs it.


def classify_subpath(
    points: tuple[Point, ...],
    against: tuple[tuple[Point, ...], ...],
    rule: FillRule = FillRule.NONZERO,
) -> tuple[PointClass, ...]:
    """For each point in `points`, is it inside or outside the shape
    defined by `against` (one or more subpaths, e.g. a shape with holes)?
    """
    return tuple(
        PointClass.INSIDE if point_in_compound(p, against, rule) else PointClass.OUTSIDE
        for p in points
    )


@dataclass(frozen=True)
class BooleanPrepResult:
    kind: BooleanKind
    subject_subpaths: tuple[tuple[Point, ...], ...]
    clip_subpaths: tuple[tuple[Point, ...], ...]
    intersections: tuple[tuple[Intersection, ...], ...]  # per (subject_i, clip_j) pair
    subject_point_classes: tuple[tuple[PointClass, ...], ...]
    clip_point_classes: tuple[tuple[PointClass, ...], ...]


def prepare_boolean(
    subject: Shape,
    clip: Shape,
    kind: BooleanKind,
    tolerance: float = DEFAULT_TOLERANCE_MM,
    rule: FillRule = FillRule.NONZERO,
) -> BooleanPrepResult:
    subject_subpaths = flatten_compound(as_compound(subject), tolerance)
    clip_subpaths = flatten_compound(as_compound(clip), tolerance)

    intersections = tuple(
        find_intersections(sp, cp) for sp in subject_subpaths for cp in clip_subpaths
    )
    subject_classes = tuple(classify_subpath(sp, clip_subpaths, rule) for sp in subject_subpaths)
    clip_classes = tuple(classify_subpath(cp, subject_subpaths, rule) for cp in clip_subpaths)

    return BooleanPrepResult(
        kind=kind,
        subject_subpaths=subject_subpaths,
        clip_subpaths=clip_subpaths,
        intersections=intersections,
        subject_point_classes=subject_classes,
        clip_point_classes=clip_classes,
    )
