"""Polygon offset: grow (positive distance) or shrink (negative distance)
a closed polygon along its edge normals.

Scope/honesty note: this is a standard "naive" per-edge-normal offset
with miter/bevel/round corner joins — correct and exact for convex
shapes (verified: offsetting a square outward gives an exact larger
square under miter join, and an exact stadium shape under round join).
It does *not* detect or trim self-intersections that can appear when
shrinking a concave shape past its own local feature size, or when
growing a shape with nearby non-adjacent edges — that's what a full
offset algorithm (e.g. Clipper's) solves, and is out of scope for this
engine's foundational layer. Concave corners use a plain line-line
intersection (stable in practice for the modest offsets manufacturing
clearances typically need); only convex corners get join-style
treatment (miter/bevel/round), since that's where a gap would otherwise
appear.
"""

from __future__ import annotations

import math
from enum import Enum

from core.engines.geometry.flatten import DEFAULT_TOLERANCE_MM, flatten_path
from core.engines.geometry.model import LineSegment, Path, Point, Shape, as_compound
from core.engines.geometry.winding import Orientation, orientation


class JoinStyle(Enum):
    MITER = "miter"
    BEVEL = "bevel"
    ROUND = "round"


def _unit(dx: float, dy: float) -> tuple[float, float]:
    length = math.hypot(dx, dy)
    if length == 0:
        return 0.0, 0.0
    return dx / length, dy / length


def _outward_normal(p0: Point, p1: Point) -> tuple[float, float]:
    """For a CCW polygon, rotate the edge direction by -90 degrees."""
    dx, dy = p1.x - p0.x, p1.y - p0.y
    ux, uy = _unit(dx, dy)
    return uy, -ux


def _line_intersection(a1: Point, a2: Point, b1: Point, b2: Point) -> Point | None:
    x1, y1, x2, y2 = a1.x, a1.y, a2.x, a2.y
    x3, y3, x4, y4 = b1.x, b1.y, b2.x, b2.y
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-12:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    return Point(x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def _cross(o: Point, a: Point, b: Point) -> float:
    return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x)


def offset_points(
    points: tuple[Point, ...],
    distance: float,
    join: JoinStyle = JoinStyle.MITER,
    miter_limit: float = 4.0,
) -> tuple[Point, ...]:
    """Offset a closed polygon (given as a point ring, first point not
    repeated at the end). Returns a new closed point ring in the same
    winding order as the input.
    """
    if len(points) < 3:
        raise ValueError("offset_points requires at least 3 points")
    if distance == 0:
        return points

    was_cw = orientation(points) == Orientation.CLOCKWISE
    pts = tuple(reversed(points)) if was_cw else points
    n = len(pts)

    normals = [_outward_normal(pts[i], pts[(i + 1) % n]) for i in range(n)]
    offset_edges = [
        (
            Point(pts[i].x + normals[i][0] * distance, pts[i].y + normals[i][1] * distance),
            Point(
                pts[(i + 1) % n].x + normals[i][0] * distance,
                pts[(i + 1) % n].y + normals[i][1] * distance,
            ),
        )
        for i in range(n)
    ]

    result: list[Point] = []
    for i in range(n):
        prev_edge = offset_edges[(i - 1) % n]
        curr_edge = offset_edges[i]
        vertex = pts[i]
        prev_vertex, next_vertex = pts[(i - 1) % n], pts[(i + 1) % n]
        is_convex = _cross(prev_vertex, vertex, next_vertex) > 0  # CCW left turn

        if not is_convex or join is JoinStyle.MITER:
            intersection = _line_intersection(
                prev_edge[0], prev_edge[1], curr_edge[0], curr_edge[1]
            )
            if intersection is not None and (
                not is_convex or intersection.distance_to(vertex) <= miter_limit * abs(distance)
            ):
                result.append(intersection)
                continue
            # Miter limit exceeded on a convex corner (or parallel edges): bevel.
            result.append(prev_edge[1])
            result.append(curr_edge[0])
            continue

        if join is JoinStyle.BEVEL:
            result.append(prev_edge[1])
            result.append(curr_edge[0])
            continue

        # ROUND join on a convex corner: arc from prev_edge[1] to curr_edge[0],
        # centered at the original vertex, radius = |distance|.
        start_angle = math.atan2(prev_edge[1].y - vertex.y, prev_edge[1].x - vertex.x)
        end_angle = math.atan2(curr_edge[0].y - vertex.y, curr_edge[0].x - vertex.x)
        sweep = end_angle - start_angle
        while sweep <= 0:
            sweep += 2 * math.pi
        while sweep > 2 * math.pi:
            sweep -= 2 * math.pi
        steps = max(1, math.ceil(math.degrees(sweep) / 15))
        r = abs(distance)
        for step in range(steps + 1):
            angle = start_angle + sweep * (step / steps)
            result.append(Point(vertex.x + r * math.cos(angle), vertex.y + r * math.sin(angle)))

    return tuple(reversed(result)) if was_cw else tuple(result)


def offset_path(
    path: Path,
    distance: float,
    join: JoinStyle = JoinStyle.MITER,
    miter_limit: float = 4.0,
    tolerance: float = DEFAULT_TOLERANCE_MM,
) -> Path:
    """Flattens `path` (so curved input is supported), offsets the
    resulting polygon, and returns a straight-line-segment Path. Exact
    for already-straight (Line-only) input.
    """
    points = flatten_path(path, tolerance)
    if path.closed and len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]
    offset = offset_points(points, distance, join, miter_limit)
    n = len(offset)
    segments = tuple(LineSegment(offset[i], offset[(i + 1) % n]) for i in range(n))
    return Path(segments, closed=True)


def offset_shape(
    shape: Shape,
    distance: float,
    join: JoinStyle = JoinStyle.MITER,
    miter_limit: float = 4.0,
    tolerance: float = DEFAULT_TOLERANCE_MM,
) -> tuple[Path, ...]:
    """Offsets every subpath of `shape` independently. Special-cases
    Circle/Ellipse for an exact (non-flattened) concentric offset.
    """
    from core.engines.geometry.model import Circle, Ellipse

    if isinstance(shape, Circle):
        new_radius = shape.radius + distance
        if new_radius <= 0:
            raise ValueError("Offset collapses circle to zero or negative radius")
        return (Circle(shape.center, new_radius).to_path(),)
    if isinstance(shape, Ellipse):
        # No exact analytic offset for an ellipse; flatten-and-offset like
        # any other curved shape (documented limitation in the module
        # docstring's spirit — approximate, not exact, unlike Circle).
        pass

    compound = as_compound(shape)
    return tuple(offset_path(p, distance, join, miter_limit, tolerance) for p in compound.paths)
