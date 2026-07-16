"""Winding, orientation, and fill-rule tests — all operate on flattened
point lists (shoelace formula), consistent with this engine's rule of
"flatten once, share the algorithm."
"""

from __future__ import annotations

from enum import Enum

from core.engines.geometry.model import Point


class Orientation(Enum):
    CLOCKWISE = "clockwise"
    COUNTER_CLOCKWISE = "counter_clockwise"
    DEGENERATE = "degenerate"  # zero area


def signed_area(points: tuple[Point, ...]) -> float:
    """Shoelace formula. Positive = counter-clockwise (standard math/SVG
    convention with y-up; if the caller's coordinate system is y-down,
    the sign convention simply flips consistently, which doesn't affect
    any comparison this engine makes).
    """
    n = len(points)
    if n < 3:
        return 0.0
    total = 0.0
    for i in range(n):
        p0, p1 = points[i], points[(i + 1) % n]
        total += p0.x * p1.y - p1.x * p0.y
    return total / 2.0


def orientation(points: tuple[Point, ...], tol: float = 1e-9) -> Orientation:
    area = signed_area(points)
    if abs(area) <= tol:
        return Orientation.DEGENERATE
    return Orientation.COUNTER_CLOCKWISE if area > 0 else Orientation.CLOCKWISE


def reverse_points(points: tuple[Point, ...]) -> tuple[Point, ...]:
    return tuple(reversed(points))


class FillRule(Enum):
    NONZERO = "nonzero"
    EVENODD = "evenodd"


def _winding_number(point: Point, polygon: tuple[Point, ...]) -> int:
    """Standard winding-number algorithm (robust for nonzero fill rule)."""
    wn = 0
    n = len(polygon)
    for i in range(n):
        p0, p1 = polygon[i], polygon[(i + 1) % n]
        if p0.y <= point.y:
            if p1.y > point.y and _is_left(p0, p1, point) > 0:
                wn += 1
        else:
            if p1.y <= point.y and _is_left(p0, p1, point) < 0:
                wn -= 1
    return wn


def _is_left(p0: Point, p1: Point, p2: Point) -> float:
    return (p1.x - p0.x) * (p2.y - p0.y) - (p2.x - p0.x) * (p1.y - p0.y)


def _crossing_count(point: Point, polygon: tuple[Point, ...]) -> int:
    count = 0
    n = len(polygon)
    for i in range(n):
        p0, p1 = polygon[i], polygon[(i + 1) % n]
        if (p0.y > point.y) != (p1.y > point.y):
            x_at_y = p0.x + (point.y - p0.y) * (p1.x - p0.x) / (p1.y - p0.y)
            if point.x < x_at_y:
                count += 1
    return count


def point_in_polygon(point: Point, polygon: tuple[Point, ...], rule: FillRule) -> bool:
    if len(polygon) < 3:
        return False
    if rule is FillRule.NONZERO:
        return _winding_number(point, polygon) != 0
    return _crossing_count(point, polygon) % 2 == 1


def point_in_compound(
    point: Point, subpaths: tuple[tuple[Point, ...], ...], rule: FillRule
) -> bool:
    """Fill-rule evaluation across multiple subpaths (e.g. a ring: outer
    boundary plus a hole) — nonzero sums winding contributions across
    every subpath before testing != 0; evenodd counts crossings across
    all subpaths before testing parity. This is the standard multi-
    subpath generalization of both rules.
    """
    if rule is FillRule.NONZERO:
        total = sum(_winding_number(point, sp) for sp in subpaths if len(sp) >= 3)
        return total != 0
    total_crossings = sum(_crossing_count(point, sp) for sp in subpaths if len(sp) >= 3)
    return total_crossings % 2 == 1
