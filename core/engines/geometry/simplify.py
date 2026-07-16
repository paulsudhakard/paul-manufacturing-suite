"""Node simplification (Douglas-Peucker) and curve smoothing
(Catmull-Rom -> cubic Bezier fit). Both operate on flattened point
lists and produce, respectively, a reduced point list and a smooth
Path built from Beziers through those points.
"""

from __future__ import annotations

from core.engines.geometry.model import BezierSegment, Path, Point


def _perpendicular_distance(point: Point, line_start: Point, line_end: Point) -> float:
    if line_start == line_end:
        return point.distance_to(line_start)
    dx, dy = line_end.x - line_start.x, line_end.y - line_start.y
    length_sq = dx * dx + dy * dy
    num = abs(dy * point.x - dx * point.y + line_end.x * line_start.y - line_end.y * line_start.x)
    return num / (length_sq**0.5)


def simplify_points(points: tuple[Point, ...], tolerance: float) -> tuple[Point, ...]:
    """Douglas-Peucker. Preserves the first and last point exactly."""
    if len(points) < 3:
        return points

    def recurse(pts: list[Point]) -> list[Point]:
        if len(pts) < 3:
            return pts
        start, end = pts[0], pts[-1]
        max_dist = -1.0
        index = -1
        for i in range(1, len(pts) - 1):
            d = _perpendicular_distance(pts[i], start, end)
            if d > max_dist:
                max_dist = d
                index = i
        if max_dist > tolerance:
            left = recurse(pts[: index + 1])
            right = recurse(pts[index:])
            return left[:-1] + right
        return [start, end]

    return tuple(recurse(list(points)))


def smooth_points(points: tuple[Point, ...], closed: bool = False, tension: float = 1.0) -> Path:
    """Fit a smooth cubic-Bezier path through `points` using Catmull-Rom
    -> Bezier control-point conversion (standard, deterministic
    technique: for each span P1->P2, control points are derived from
    the neighboring points P0 and P3). `tension` in [0, 1]; 1.0 is a
    standard Catmull-Rom curve, lower values pull it straighter.
    """
    n = len(points)
    if n < 2:
        raise ValueError("smooth_points requires at least 2 points")
    if n == 2:
        from core.engines.geometry.model import LineSegment

        return Path((LineSegment(points[0], points[1]),), closed=closed)

    def get(i: int) -> Point:
        if closed:
            return points[i % n]
        return points[max(0, min(n - 1, i))]

    segments = []
    span_count = n if closed else n - 1
    k = tension / 6.0
    for i in range(span_count):
        p0, p1, p2, p3 = get(i - 1), get(i), get(i + 1), get(i + 2)
        c1 = Point(p1.x + (p2.x - p0.x) * k, p1.y + (p2.y - p0.y) * k)
        c2 = Point(p2.x - (p3.x - p1.x) * k, p2.y - (p3.y - p1.y) * k)
        segments.append(BezierSegment(p1, c1, c2, p2))
    return Path(tuple(segments), closed=closed)
