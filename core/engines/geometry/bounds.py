"""Bounding box: exact per segment type (not just control-point bounds),
since "accuracy is more important than speed" for this engine.
"""

from __future__ import annotations

import math

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


class BoundingBox:
    __slots__ = ("min_x", "min_y", "max_x", "max_y")

    def __init__(self, min_x: float, min_y: float, max_x: float, max_y: float) -> None:
        self.min_x, self.min_y, self.max_x, self.max_y = min_x, min_y, max_x, max_y

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    def union(self, other: "BoundingBox") -> "BoundingBox":
        return BoundingBox(
            min(self.min_x, other.min_x),
            min(self.min_y, other.min_y),
            max(self.max_x, other.max_x),
            max(self.max_y, other.max_y),
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BoundingBox):
            return NotImplemented
        return (self.min_x, self.min_y, self.max_x, self.max_y) == (
            other.min_x,
            other.min_y,
            other.max_x,
            other.max_y,
        )

    def __repr__(self) -> str:
        return f"BoundingBox(min=({self.min_x},{self.min_y}), max=({self.max_x},{self.max_y}))"


def _point_bbox(p: Point) -> BoundingBox:
    return BoundingBox(p.x, p.y, p.x, p.y)


def _bezier_extrema_t(p0: float, p1: float, p2: float, p3: float) -> list[float]:
    """Roots of the derivative of a cubic Bezier's single coordinate,
    restricted to [0, 1] — the standard way to get a tight axis-aligned
    bound instead of the (looser) control-point bound.
    """
    a = -p0 + 3 * p1 - 3 * p2 + p3
    b = 2 * (p0 - 2 * p1 + p2)
    c = p1 - p0
    roots = []
    if abs(a) < 1e-12:
        if abs(b) > 1e-12:
            roots.append(-c / b)
    else:
        disc = b * b - 4 * a * c
        if disc >= 0:
            sqrt_disc = math.sqrt(disc)
            roots.append((-b + sqrt_disc) / (2 * a))
            roots.append((-b - sqrt_disc) / (2 * a))
    return [t for t in roots if 0.0 <= t <= 1.0]


def _bezier_bbox(segment: BezierSegment) -> BoundingBox:
    xs = [segment.start.x, segment.end.x]
    ys = [segment.start.y, segment.end.y]
    for t in _bezier_extrema_t(
        segment.start.x, segment.control1.x, segment.control2.x, segment.end.x
    ):
        xs.append(segment.point_at(t).x)
    for t in _bezier_extrema_t(
        segment.start.y, segment.control1.y, segment.control2.y, segment.end.y
    ):
        ys.append(segment.point_at(t).y)
    return BoundingBox(min(xs), min(ys), max(xs), max(ys))


def _angle_in_sweep(angle: float, start_angle: float, sweep: float) -> bool:
    if sweep >= 0:
        delta = (angle - start_angle) % (2 * math.pi)
        return delta <= sweep
    delta = (start_angle - angle) % (2 * math.pi)
    return delta <= -sweep


def _arc_bbox(segment: ArcSegment) -> BoundingBox:
    xs = [segment.start.x, segment.end.x]
    ys = [segment.start.y, segment.end.y]
    cx, cy, r = segment.center.x, segment.center.y, segment.radius
    start_angle = segment.start_angle()
    sweep = segment.sweep_angle()
    for cardinal in (0, math.pi / 2, math.pi, 3 * math.pi / 2):
        if _angle_in_sweep(cardinal, start_angle, sweep):
            xs.append(cx + r * math.cos(cardinal))
            ys.append(cy + r * math.sin(cardinal))
    return BoundingBox(min(xs), min(ys), max(xs), max(ys))


def segment_bbox(segment: Segment) -> BoundingBox:
    if isinstance(segment, LineSegment):
        return _point_bbox(segment.start).union(_point_bbox(segment.end))
    if isinstance(segment, BezierSegment):
        return _bezier_bbox(segment)
    if isinstance(segment, ArcSegment):
        return _arc_bbox(segment)
    raise TypeError(f"Unknown segment type: {type(segment)}")


def path_bbox(path: Path) -> BoundingBox:
    if not path.segments:
        raise ValueError("Cannot compute bounding box of an empty path")
    boxes = [segment_bbox(s) for s in path.segments]
    result = boxes[0]
    for box in boxes[1:]:
        result = result.union(box)
    return result


def compound_bbox(compound: CompoundPath) -> BoundingBox:
    non_empty = [p for p in compound.paths if p.segments]
    if not non_empty:
        raise ValueError("Cannot compute bounding box of an empty compound path")
    boxes = [path_bbox(p) for p in non_empty]
    result = boxes[0]
    for box in boxes[1:]:
        result = result.union(box)
    return result


def bounding_box(shape: Shape) -> BoundingBox:
    return compound_bbox(as_compound(shape))
