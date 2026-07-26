"""Shared analysis helpers for the Manufacturing Validator and Repair
modules. Kept separate so both consume the exact same classification
logic rather than each re-deriving it.

Honesty note (applies to every function below that touches "is this
shape too thin / too narrow / too close"): true robust answers require
polygon boolean union (merging touching/overlapping regions) and
medial-axis analysis, out of scope here (Geometry Engine ships boolean
*preparation* only, not full CSG). Every function below is a
deterministic, documented **proxy** — accurate for the common, simple
cases a seal outline actually produces (nested holes, distinct islands,
locally narrow necks within one subpath), not a general topological
solver.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from core.engines.geometry.flatten import flatten_path
from core.engines.geometry.measure import polygon_area
from core.engines.geometry.model import CompoundPath, Path, Point
from core.engines.geometry.winding import FillRule, Orientation, orientation, point_in_polygon


@dataclass(frozen=True)
class SubpathInfo:
    index: int
    path: Path
    ring: tuple[Point, ...]  # flattened, closing point removed
    area: float  # unsigned
    orientation: Orientation
    is_hole: bool  # nested inside another subpath with opposite winding


def classify_subpaths(compound: CompoundPath, tolerance: float) -> tuple[SubpathInfo, ...]:
    prepared = []
    for i, path in enumerate(compound.paths):
        flat = flatten_path(path, tolerance)
        ring = flat[:-1] if len(flat) > 1 and flat[0] == flat[-1] else flat
        prepared.append((i, path, ring))

    orientations = {}
    for i, path, ring in prepared:
        orientations[i] = orientation(ring) if len(ring) >= 3 else Orientation.DEGENERATE

    result = []
    for i, path, ring in prepared:
        if len(ring) < 3:
            result.append(SubpathInfo(i, path, ring, 0.0, Orientation.DEGENERATE, False))
            continue
        area = polygon_area(ring)
        orient = orientations[i]
        is_hole = False
        sample = _representative_point(ring)
        for j, _other_path, other_ring in prepared:
            if j == i or len(other_ring) < 3:
                continue
            if not point_in_polygon(sample, other_ring, FillRule.NONZERO):
                continue
            # Contained AND opposite winding from its container = a true
            # hole (standard nonzero-fill-rule semantics). Contained with
            # the *same* winding is a separate solid piece (an island),
            # not a hole — containment alone can't tell the two apart.
            if orientations[j] != Orientation.DEGENERATE and orient != orientations[j]:
                is_hole = True
                break
        result.append(SubpathInfo(i, path, ring, area, orient, is_hole))
    return tuple(result)


def _representative_point(ring: tuple[Point, ...]) -> Point:
    """A point guaranteed inside a simple polygon: the midpoint between
    the lowest vertex and the average of its two neighbors — robust for
    both convex and mildly concave rings, cheaper than a full
    centroid-inside check.
    """
    n = len(ring)
    idx = min(range(n), key=lambda k: (ring[k].y, ring[k].x))
    prev_p, cur_p, next_p = ring[(idx - 1) % n], ring[idx], ring[(idx + 1) % n]
    mx = (prev_p.x + next_p.x) / 2
    my = (prev_p.y + next_p.y) / 2
    return Point((cur_p.x + mx) / 2, (cur_p.y + my) / 2)


def min_distance_between_rings(
    ring_a: tuple[Point, ...], ring_b: tuple[Point, ...]
) -> tuple[float, int, int]:
    """Minimum distance between any edge of ring_a and any edge of
    ring_b. O(n*m) — fine at manufacturing scale. Returns
    (distance, edge_index_a, edge_index_b).
    """
    best = math.inf
    best_i = best_j = -1
    na, nb = len(ring_a), len(ring_b)
    for i in range(na):
        a1, a2 = ring_a[i], ring_a[(i + 1) % na]
        for j in range(nb):
            b1, b2 = ring_b[j], ring_b[(j + 1) % nb]
            d = _segment_segment_distance(a1, a2, b1, b2)
            if d < best:
                best, best_i, best_j = d, i, j
    return best, best_i, best_j


def min_self_distance(
    ring: tuple[Point, ...], arc_length_ratio: float = 4.0
) -> tuple[float, int, int]:
    """Minimum distance between non-adjacent edges of the *same* ring —
    the narrow-neck / weak-bridge proxy: a small value means two parts
    of the outline pass close to each other without being connected there.

    Guards against a critical false positive on smooth curves: a finely
    tessellated circle/arc has many edges that are topologically distinct
    but geometrically close purely because of tessellation density (two
    points a few segments apart on a gentle curve are naturally near each
    other). That is NOT a narrow neck. A genuine neck is characterized by
    two points that are close in straight-line distance but *far apart*
    along the boundary. `arc_length_ratio` enforces this: a candidate
    pair only counts if the shorter path along the ring between them is
    at least `arc_length_ratio` times their straight-line distance.
    """
    n = len(ring)
    if n < 3:
        return math.inf, -1, -1

    cumulative = [0.0] * (n + 1)
    for i in range(n):
        cumulative[i + 1] = cumulative[i] + ring[i].distance_to(ring[(i + 1) % n])
    total_perimeter = cumulative[n]

    def arc_separation(i: int, j: int) -> float:
        forward = abs(cumulative[j] - cumulative[i])
        return min(forward, total_perimeter - forward)

    best = math.inf
    best_i = best_j = -1
    for i in range(n):
        a1, a2 = ring[i], ring[(i + 1) % n]
        for j in range(i + 2, n):
            if (j + 1) % n == i:
                continue  # adjacent at the wrap-around
            b1, b2 = ring[j], ring[(j + 1) % n]
            d = _segment_segment_distance(a1, a2, b1, b2)
            if d >= best:
                continue
            separation = arc_separation(i, j)
            if separation < arc_length_ratio * max(d, 1e-9):
                continue  # too close along the boundary — tessellation artifact, not a neck
            best, best_i, best_j = d, i, j
    return best, best_i, best_j


def _point_segment_distance(p: Point, a: Point, b: Point) -> float:
    dx, dy = b.x - a.x, b.y - a.y
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return p.distance_to(a)
    t = max(0.0, min(1.0, ((p.x - a.x) * dx + (p.y - a.y) * dy) / length_sq))
    proj = Point(a.x + t * dx, a.y + t * dy)
    return p.distance_to(proj)


def _segment_segment_distance(a1: Point, a2: Point, b1: Point, b2: Point) -> float:
    if _segments_intersect(a1, a2, b1, b2):
        return 0.0
    return min(
        _point_segment_distance(a1, b1, b2),
        _point_segment_distance(a2, b1, b2),
        _point_segment_distance(b1, a1, a2),
        _point_segment_distance(b2, a1, a2),
    )


def _cross(o: Point, a: Point, b: Point) -> float:
    return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x)


def _segments_intersect(a1: Point, a2: Point, b1: Point, b2: Point) -> bool:
    d1 = _cross(b1, b2, a1)
    d2 = _cross(b1, b2, a2)
    d3 = _cross(a1, a2, b1)
    d4 = _cross(a1, a2, b2)
    return (d1 * d2 < 0) and (d3 * d4 < 0)


def interior_angle_degrees(prev_point: Point, vertex: Point, next_point: Point) -> float:
    v1 = (prev_point.x - vertex.x, prev_point.y - vertex.y)
    v2 = (next_point.x - vertex.x, next_point.y - vertex.y)
    len1, len2 = math.hypot(*v1), math.hypot(*v2)
    if len1 == 0 or len2 == 0:
        return 180.0
    cos_angle = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (len1 * len2)))
    return math.degrees(math.acos(cos_angle))


def path_node_density(path: Path, tolerance: float) -> float:
    """Nodes per mm of the flattened polyline's total length."""
    ring = flatten_path(path, tolerance)
    if len(ring) < 2:
        return 0.0
    length = sum(ring[i].distance_to(ring[i + 1]) for i in range(len(ring) - 1))
    if length == 0:
        return math.inf
    return len(ring) / length
