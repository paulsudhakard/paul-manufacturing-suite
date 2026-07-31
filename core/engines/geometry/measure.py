"""Area, perimeter, centroid.

Area/centroid use the flattened polygon (exact for Line/Polygon input,
tolerance-bounded approximation for Bezier/Arc — accurate to whatever
tolerance `flatten_*` was given, default 0.01mm). Perimeter sums exact
segment lengths where a closed form exists (Line: exact; Arc: exact via
radius*|sweep|) and flattened chord lengths only for Bezier, where no
simple closed form exists.
"""

from __future__ import annotations

from core.engines.geometry.flatten import DEFAULT_TOLERANCE_MM, flatten_bezier
from core.engines.geometry.model import (
    ArcSegment,
    BezierSegment,
    CompoundPath,
    LineSegment,
    Path,
    Point,
    Segment,
    Shape,
    as_compound,
)
from core.engines.geometry.winding import signed_area


def polygon_area(points: tuple[Point, ...]) -> float:
    """Unsigned area of a flattened, closed point ring."""
    return abs(signed_area(points))


def polygon_centroid(points: tuple[Point, ...]) -> Point:
    """Area-weighted centroid of a flattened, closed point ring."""
    n = len(points)
    if n < 3:
        raise ValueError("Centroid requires at least 3 points")
    area2 = 0.0
    cx = cy = 0.0
    for i in range(n):
        p0, p1 = points[i], points[(i + 1) % n]
        cross = p0.x * p1.y - p1.x * p0.y
        area2 += cross
        cx += (p0.x + p1.x) * cross
        cy += (p0.y + p1.y) * cross
    if abs(area2) < 1e-12:
        # Degenerate (zero-area) ring: fall back to the arithmetic mean.
        return Point(sum(p.x for p in points) / n, sum(p.y for p in points) / n)
    factor = 1 / (3 * area2)
    return Point(cx * factor, cy * factor)


def _segment_length(segment: Segment, tolerance: float) -> float:
    if isinstance(segment, LineSegment):
        return segment.start.distance_to(segment.end)
    if isinstance(segment, ArcSegment):
        return segment.radius * abs(segment.sweep_angle())
    if isinstance(segment, BezierSegment):
        points = flatten_bezier(segment, tolerance) + (segment.end,)
        return sum(points[i].distance_to(points[i + 1]) for i in range(len(points) - 1))
    raise TypeError(f"Unknown segment type: {type(segment)}")


def path_perimeter(path: Path, tolerance: float = DEFAULT_TOLERANCE_MM) -> float:
    return sum(_segment_length(s, tolerance) for s in path.segments)


def compound_perimeter(compound: CompoundPath, tolerance: float = DEFAULT_TOLERANCE_MM) -> float:
    return sum(path_perimeter(p, tolerance) for p in compound.paths)


def perimeter(shape: Shape, tolerance: float = DEFAULT_TOLERANCE_MM) -> float:
    return compound_perimeter(as_compound(shape), tolerance)


def area(shape: Shape, tolerance: float = DEFAULT_TOLERANCE_MM) -> float:
    """Net area across all subpaths, honoring winding as sign (so a hole
    subpath wound opposite to its outer boundary subtracts) — this is
    the standard "signed area sum" definition for compound shapes with
    holes; the fill-rule-specific area (nonzero vs evenodd, which can
    differ for self-overlapping shapes) is out of scope here since that
    needs manufacturing-level interpretation this engine defers.
    """
    from core.engines.geometry.flatten import flatten_compound

    subpaths = flatten_compound(as_compound(shape), tolerance)
    return sum(signed_area(sp) for sp in subpaths if len(sp) >= 3)


def centroid(shape: Shape, tolerance: float = DEFAULT_TOLERANCE_MM) -> Point:
    """Area-weighted centroid across all subpaths (holes' negative area
    correctly pulls the centroid away from the hole).
    """
    from core.engines.geometry.flatten import flatten_compound

    subpaths = flatten_compound(as_compound(shape), tolerance)
    total_area = 0.0
    cx = cy = 0.0
    for sp in subpaths:
        if len(sp) < 3:
            continue
        sub_area = signed_area(sp)
        sub_centroid = polygon_centroid(sp)
        cx += sub_centroid.x * sub_area
        cy += sub_centroid.y * sub_area
        total_area += sub_area
    if abs(total_area) < 1e-12:
        raise ValueError("Cannot compute centroid of a zero-area shape")
    return Point(cx / total_area, cy / total_area)
