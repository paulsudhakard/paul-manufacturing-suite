"""Curve flattening: Bezier/Arc segments -> polylines, within a tolerance.
Everything downstream that needs a plain point list (measure, offset,
boolean_prep, self-intersection checks in validation) flattens first
rather than re-implementing curve math per algorithm.
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
)

DEFAULT_TOLERANCE_MM = 0.01


def flatten_bezier(
    segment: BezierSegment, tolerance: float = DEFAULT_TOLERANCE_MM
) -> tuple[Point, ...]:
    """Adaptive subdivision by flatness (distance of control points from
    the chord). Returns points including `start`, excluding `end`.
    """

    def flat_enough(s: BezierSegment) -> bool:
        chord = s.end.distance_to(s.start)
        if chord == 0:
            d1 = s.control1.distance_to(s.start)
            d2 = s.control2.distance_to(s.end)
            return max(d1, d2) <= tolerance

        def dist_to_line(p: Point) -> float:
            num = abs(
                (s.end.x - s.start.x) * (s.start.y - p.y)
                - (s.start.x - p.x) * (s.end.y - s.start.y)
            )
            return num / chord

        return dist_to_line(s.control1) <= tolerance and dist_to_line(s.control2) <= tolerance

    def subdivide(s: BezierSegment) -> tuple[BezierSegment, BezierSegment]:
        p01 = _midpoint(s.start, s.control1)
        p12 = _midpoint(s.control1, s.control2)
        p23 = _midpoint(s.control2, s.end)
        p012 = _midpoint(p01, p12)
        p123 = _midpoint(p12, p23)
        p0123 = _midpoint(p012, p123)
        return (
            BezierSegment(s.start, p01, p012, p0123),
            BezierSegment(p0123, p123, p23, s.end),
        )

    points: list[Point] = []

    def recurse(s: BezierSegment, depth: int) -> None:
        if depth >= 24 or flat_enough(s):
            points.append(s.start)
            return
        left, right = subdivide(s)
        recurse(left, depth + 1)
        recurse(right, depth + 1)

    recurse(segment, 0)
    return tuple(points)


def _midpoint(a: Point, b: Point) -> Point:
    return Point((a.x + b.x) / 2, (a.y + b.y) / 2)


def flatten_arc(
    segment: ArcSegment, tolerance: float = DEFAULT_TOLERANCE_MM
) -> tuple[Point, ...]:
    """Uniform angular subdivision sized so the chord-to-arc sagitta
    error stays within `tolerance` (`theta = 2*acos(1 - tol/r)`).
    Returns points including `start`, excluding `end`.
    """
    r = segment.radius
    if r <= 0:
        return (segment.start,)
    ratio = max(0.0, min(1.0, 1 - tolerance / r))
    max_angle_step = 2 * math.acos(ratio) if ratio < 1 else math.pi / 2
    max_angle_step = max(max_angle_step, math.radians(1))

    sweep = segment.sweep_angle()
    steps = max(1, math.ceil(abs(sweep) / max_angle_step))
    start_angle = segment.start_angle()
    points = []
    for i in range(steps):
        angle = start_angle + sweep * (i / steps)
        points.append(
            Point(segment.center.x + r * math.cos(angle), segment.center.y + r * math.sin(angle))
        )
    return tuple(points)


def arc_to_beziers(
    segment: ArcSegment, max_span_degrees: float = 90.0
) -> tuple[BezierSegment, ...]:
    """Approximate a circular arc with cubic Beziers, split into chunks
    of at most `max_span_degrees` (kappa formula; exact to within a few
    hundredths of a percent for <=90-degree spans).
    """
    sweep = segment.sweep_angle()
    max_span = math.radians(max_span_degrees)
    steps = max(1, math.ceil(abs(sweep) / max_span))
    step_angle = sweep / steps
    r = segment.radius
    start_angle = segment.start_angle()
    kappa = 4 / 3 * math.tan(step_angle / 4)

    beziers = []
    for i in range(steps):
        a0 = start_angle + step_angle * i
        a1 = start_angle + step_angle * (i + 1)
        p0 = Point(segment.center.x + r * math.cos(a0), segment.center.y + r * math.sin(a0))
        p1 = Point(segment.center.x + r * math.cos(a1), segment.center.y + r * math.sin(a1))
        c0 = Point(p0.x - kappa * r * math.sin(a0), p0.y + kappa * r * math.cos(a0))
        c1 = Point(p1.x + kappa * r * math.sin(a1), p1.y - kappa * r * math.cos(a1))
        beziers.append(BezierSegment(p0, c0, c1, p1))
    return tuple(beziers)


def flatten_segment(segment: Segment, tolerance: float = DEFAULT_TOLERANCE_MM) -> tuple[Point, ...]:
    if isinstance(segment, LineSegment):
        return (segment.start,)
    if isinstance(segment, BezierSegment):
        return flatten_bezier(segment, tolerance)
    if isinstance(segment, ArcSegment):
        return flatten_arc(segment, tolerance)
    raise TypeError(f"Unknown segment type: {type(segment)}")


def flatten_path(path: Path, tolerance: float = DEFAULT_TOLERANCE_MM) -> tuple[Point, ...]:
    """Polyline for one subpath, including the final end point."""
    if not path.segments:
        return ()
    points: list[Point] = []
    for segment in path.segments:
        points.extend(flatten_segment(segment, tolerance))
    points.append(path.segments[-1].end)
    return tuple(points)


def flatten_compound(
    compound: CompoundPath, tolerance: float = DEFAULT_TOLERANCE_MM
) -> tuple[tuple[Point, ...], ...]:
    return tuple(flatten_path(p, tolerance) for p in compound.paths)
