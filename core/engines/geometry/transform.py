"""2D affine transforms: translate, rotate, scale, mirror, and
composition of arbitrary matrices.

Matrix form (row-vector, SVG/CorelDRAW convention):
    x' = a*x + c*y + e
    y' = b*x + d*y + f

Note on arcs under transform: a uniform-scale transform (sx == sy,
combined with any rotation/translation) maps a circular arc to another
circular arc, so `apply_transform` keeps `ArcSegment` exact in that case.
A non-uniform scale would turn a circle into an ellipse — an ArcSegment
can't represent that exactly, so in that case the arc is converted to
its Bezier approximation before transforming, keeping the *shape*
correct rather than silently producing a wrong circular arc.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

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


@dataclass(frozen=True)
class Transform:
    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    e: float = 0.0
    f: float = 0.0

    def apply_point(self, p: Point) -> Point:
        return Point(self.a * p.x + self.c * p.y + self.e, self.b * p.x + self.d * p.y + self.f)

    def then(self, other: "Transform") -> "Transform":
        """Compose: apply `self` first, then `other`."""
        return Transform(
            a=other.a * self.a + other.c * self.b,
            b=other.b * self.a + other.d * self.b,
            c=other.a * self.c + other.c * self.d,
            d=other.b * self.c + other.d * self.d,
            e=other.a * self.e + other.c * self.f + other.e,
            f=other.b * self.e + other.d * self.f + other.f,
        )

    def is_uniform_scale(self, tol: float = 1e-9) -> bool:
        sx = math.hypot(self.a, self.b)
        sy = math.hypot(self.c, self.d)
        return abs(sx - sy) <= tol


IDENTITY = Transform()


def translate(dx: float, dy: float) -> Transform:
    return Transform(e=dx, f=dy)


def rotate(angle_radians: float, origin: Point = Point(0, 0)) -> Transform:
    cos_a, sin_a = math.cos(angle_radians), math.sin(angle_radians)
    rot = Transform(a=cos_a, b=sin_a, c=-sin_a, d=cos_a)
    return translate(-origin.x, -origin.y).then(rot).then(translate(origin.x, origin.y))


def scale(sx: float, sy: float | None = None, origin: Point = Point(0, 0)) -> Transform:
    sy = sx if sy is None else sy
    sc = Transform(a=sx, d=sy)
    return translate(-origin.x, -origin.y).then(sc).then(translate(origin.x, origin.y))


def mirror_x(origin_x: float = 0.0) -> Transform:
    """Mirror across the vertical line x = origin_x."""
    return scale(-1, 1, origin=Point(origin_x, 0))


def mirror_y(origin_y: float = 0.0) -> Transform:
    """Mirror across the horizontal line y = origin_y."""
    return scale(1, -1, origin=Point(0, origin_y))


def _transform_segment(segment: Segment, t: Transform) -> Segment | tuple[Segment, ...]:
    if isinstance(segment, LineSegment):
        return LineSegment(t.apply_point(segment.start), t.apply_point(segment.end))
    if isinstance(segment, BezierSegment):
        return BezierSegment(
            t.apply_point(segment.start),
            t.apply_point(segment.control1),
            t.apply_point(segment.control2),
            t.apply_point(segment.end),
        )
    if isinstance(segment, ArcSegment):
        if t.is_uniform_scale():
            new_radius = segment.radius * math.hypot(t.a, t.b)
            det = t.a * t.d - t.b * t.c  # reflection (det < 0) flips sweep direction
            clockwise = segment.clockwise if det > 0 else not segment.clockwise
            return ArcSegment(
                t.apply_point(segment.start),
                t.apply_point(segment.end),
                t.apply_point(segment.center),
                new_radius,
                clockwise,
            )
        from core.engines.geometry.flatten import arc_to_beziers

        beziers = arc_to_beziers(segment)
        return tuple(_transform_segment(b, t) for b in beziers)  # type: ignore[misc]
    raise TypeError(f"Unknown segment type: {type(segment)}")


def apply_transform_path(path: Path, t: Transform) -> Path:
    new_segments: list[Segment] = []
    for segment in path.segments:
        result = _transform_segment(segment, t)
        if isinstance(result, tuple):
            new_segments.extend(result)
        else:
            new_segments.append(result)
    return Path(tuple(new_segments), closed=path.closed)


def apply_transform(shape: Shape, t: Transform) -> CompoundPath:
    compound = as_compound(shape)
    return CompoundPath(tuple(apply_transform_path(p, t) for p in compound.paths))
