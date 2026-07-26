"""Manufacturing Repair — deterministic only, no AI, no scoring. Each
function is a pure, fixed-rule transformation driven entirely by
`RuleSet` thresholds, returning a `RepairResult` with an action log
(same audit-trail pattern as core.engines.geometry.repair).

Every "fix" here is a documented, deliberately simple correction, not a
claim of manufacturing-optimal geometry — see each function's docstring
for exactly what it does and doesn't guarantee.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from core.engines.geometry.measure import area as compound_area
from core.engines.geometry.measure import perimeter as compound_perimeter
from core.engines.geometry.model import ArcSegment, CompoundPath, LineSegment, Path, Point
from core.engines.manufacturing.analysis_utils import (
    classify_subpaths,
    interior_angle_degrees,
    min_self_distance,
)
from core.engines.manufacturing.rules import RuleSet


@dataclass(frozen=True)
class ManufacturingRepairResult:
    compound: CompoundPath
    actions: tuple[str, ...]
    similarity: float  # 0..1, see `_similarity_score`


def _similarity_score(before: CompoundPath, after: CompoundPath, tolerance: float) -> float:
    """A simple, deterministic area+perimeter similarity metric (1.0 =
    identical, decreasing as area/perimeter diverge) — "preserve visual
    similarity" made measurable and auditable, not a claim of perceptual
    similarity in any rigorous sense.
    """
    try:
        area_before = abs(compound_area(before, tolerance)) or 1e-9
        area_after = abs(compound_area(after, tolerance))
        perim_before = compound_perimeter(before, tolerance) or 1e-9
        perim_after = compound_perimeter(after, tolerance)
    except Exception:
        return 0.0
    area_ratio = min(area_before, area_after) / max(area_before, area_after)
    perim_ratio = min(perim_before, perim_after) / max(perim_before, perim_after)
    return (area_ratio + perim_ratio) / 2


def remove_tiny_holes(compound: CompoundPath, rule_set: RuleSet) -> tuple[CompoundPath, list[str]]:
    infos = classify_subpaths(compound, rule_set.flatten_tolerance_mm)
    keep_indices = {
        info.index
        for info in infos
        if not (info.is_hole and 0 < info.area < rule_set.min_enclosed_area_mm2)
    }
    removed = len(infos) - len(keep_indices)
    new_paths = tuple(p for i, p in enumerate(compound.paths) if i in keep_indices)
    actions = (
        [f"removed {removed} tiny hole(s) below {rule_set.min_enclosed_area_mm2}mm2"]
        if removed
        else []
    )
    return CompoundPath(new_paths), actions


def merge_tiny_islands(compound: CompoundPath, rule_set: RuleSet) -> tuple[CompoundPath, list[str]]:
    """"Merges" a tiny, non-hole island into the main body via a
    zero-width keyhole slit: a line out from the nearest point on the
    main body to the nearest point on the island, around the island,
    and back along the same line. This is a standard, real laser-cutting
    technique for attaching an otherwise-loose piece to its parent
    outline (the kerf itself gives the "slit" physical width on the cut
    material) — not a true polygon union (which would require boolean
    ops this engine doesn't implement), but the manufacturing-correct
    outcome for "this island must not fall out" is the same either way.
    """
    infos = classify_subpaths(compound, rule_set.flatten_tolerance_mm)
    if not infos:
        return compound, []
    main_info = max(infos, key=lambda i: i.area)
    actions = []
    kept_paths: list[Path] = [compound.paths[main_info.index]]
    main_ring = list(main_info.ring)

    for info in infos:
        if info.index == main_info.index:
            continue
        if info.is_hole:
            kept_paths.append(compound.paths[info.index])
            continue
        if info.area <= 0 or info.area >= rule_set.min_enclosed_area_mm2:
            kept_paths.append(compound.paths[info.index])
            continue
        if not info.ring:
            continue

        # Nearest point pair between main body and this island.
        best = min(
            ((mp, ip) for mp in main_ring for ip in info.ring),
            key=lambda pair: pair[0].distance_to(pair[1]),
        )
        main_point, island_point = best
        if main_point.distance_to(island_point) > rule_set.island_merge_search_radius_mm:
            # too far — leave as-is, don't fabricate a long slit
            kept_paths.append(compound.paths[info.index])
            continue

        island_ring = info.ring
        start_idx = island_ring.index(island_point)
        reordered_island = island_ring[start_idx:] + island_ring[:start_idx] + (island_point,)

        segments = [LineSegment(main_point, island_point)]
        segments += [
            LineSegment(reordered_island[k], reordered_island[k + 1])
            for k in range(len(reordered_island) - 1)
        ]
        segments.append(LineSegment(island_point, main_point))

        main_idx_in_ring = main_ring.index(main_point)
        # Splice the keyhole segments into the main ring at main_point.
        new_main_ring = (
            main_ring[: main_idx_in_ring + 1]
            + [s.end for s in segments]
            + main_ring[main_idx_in_ring + 1 :]
        )
        main_ring = new_main_ring
        actions.append(
            f"merged tiny island (subpath {info.index}, area {info.area:.4g}mm2) via keyhole"
        )

    if actions:
        merged_segments = tuple(
            LineSegment(main_ring[i], main_ring[(i + 1) % len(main_ring)])
            for i in range(len(main_ring))
        )
        kept_paths[0] = Path(merged_segments, closed=True)

    return CompoundPath(tuple(kept_paths)), actions


def round_sharp_corners(
    compound: CompoundPath, rule_set: RuleSet
) -> tuple[CompoundPath, list[str]]:
    """Fillets every interior vertex sharper than
    `sharp_corner_angle_threshold_degrees` with an arc of radius
    `corner_radius_mm`, tangent to both adjacent edges. Standard
    corner-fillet construction: trim back along each edge by
    `radius * tan(interior_angle/2)... ` (using the exterior half-angle)
    and connect the trim points with a circular arc centered at the
    offset bisector point.
    """
    radius = rule_set.corner_radius_mm
    threshold = rule_set.sharp_corner_angle_threshold_degrees
    new_paths = []
    actions = []

    for path in compound.paths:
        if not path.closed or len(path.segments) < 3:
            new_paths.append(path)
            continue
        # Only handles polygons made of LineSegments (the common case for
        # a repaired/simplified outline); paths containing curves pass
        # through unchanged rather than risk an incorrect fillet.
        if not all(isinstance(s, LineSegment) for s in path.segments):
            new_paths.append(path)
            continue

        pts = [s.start for s in path.segments]
        n = len(pts)
        new_segments: list = []
        any_rounded = False
        for i in range(n):
            prev_p, vertex, next_p = pts[(i - 1) % n], pts[i], pts[(i + 1) % n]
            angle = interior_angle_degrees(prev_p, vertex, next_p)
            if angle >= threshold:
                new_segments.append(LineSegment(vertex, next_p))
                continue

            v1 = _unit_vector(vertex, prev_p)
            v2 = _unit_vector(vertex, next_p)
            half_angle = math.radians(angle) / 2
            trim = radius / math.tan(half_angle) if math.tan(half_angle) != 0 else 0.0
            trim = min(trim, vertex.distance_to(prev_p) / 2, vertex.distance_to(next_p) / 2)

            trim_in = Point(vertex.x + v1[0] * trim, vertex.y + v1[1] * trim)
            trim_out = Point(vertex.x + v2[0] * trim, vertex.y + v2[1] * trim)
            mid = Point((v1[0] + v2[0]) / 2 + vertex.x, (v1[1] + v2[1]) / 2 + vertex.y)
            bisector = _unit_vector(vertex, mid)
            center_dist = math.hypot(trim, radius) if trim else radius
            center = Point(
                vertex.x + bisector[0] * center_dist, vertex.y + bisector[1] * center_dist
            )

            # Replace the previous segment's end with trim_in, insert the arc, continue to trim_out.
            if new_segments and isinstance(new_segments[-1], LineSegment):
                new_segments[-1] = LineSegment(new_segments[-1].start, trim_in)
            clockwise = _cross(vertex, prev_p, next_p) > 0
            new_segments.append(ArcSegment(trim_in, trim_out, center, radius, clockwise))
            new_segments.append(LineSegment(trim_out, next_p))
            any_rounded = True

        if any_rounded:
            actions.append(f"rounded sharp corners with {radius}mm radius")
        new_paths.append(Path(tuple(new_segments), closed=True))

    return CompoundPath(tuple(new_paths)), actions


def _unit_vector(a: Point, b: Point) -> tuple[float, float]:
    length = a.distance_to(b)
    if length == 0:
        return (0.0, 0.0)
    return ((b.x - a.x) / length, (b.y - a.y) / length)


def _cross(o: Point, a: Point, b: Point) -> float:
    return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x)


def widen_weak_bridges(compound: CompoundPath, rule_set: RuleSet) -> tuple[CompoundPath, list[str]]:
    """For each flagged narrow-neck pair of edges, nudges the two
    involved vertices apart along the local perpendicular until they
    reach `min_bridge_width_mm`. A coarse, local, deterministic
    correction — not a guarantee the rest of the shape stays perfectly
    proportioned around the nudge, consistent with this module's
    documented "proxy, not full solver" scope.
    """
    new_paths = []
    actions = []
    for path in compound.paths:
        if not path.closed or len(path.segments) < 4 or not all(
            isinstance(s, LineSegment) for s in path.segments
        ):
            new_paths.append(path)
            continue
        pts = [s.start for s in path.segments]
        distance, i, j = min_self_distance(tuple(pts))
        if distance >= rule_set.min_bridge_width_mm or distance == 0:
            new_paths.append(path)
            continue

        n = len(pts)
        a1, a2 = pts[i], pts[(i + 1) % n]
        b1, b2 = pts[j], pts[(j + 1) % n]
        mid_a = Point((a1.x + a2.x) / 2, (a1.y + a2.y) / 2)
        mid_b = Point((b1.x + b2.x) / 2, (b1.y + b2.y) / 2)
        dx, dy = mid_b.x - mid_a.x, mid_b.y - mid_a.y
        current = math.hypot(dx, dy) or 1e-9
        push = (rule_set.min_bridge_width_mm - distance) / 2
        ux, uy = dx / current, dy / current

        pts[i] = Point(a1.x - ux * push, a1.y - uy * push)
        pts[(i + 1) % n] = Point(a2.x - ux * push, a2.y - uy * push)
        pts[j] = Point(b1.x + ux * push, b1.y + uy * push)
        pts[(j + 1) % n] = Point(b2.x + ux * push, b2.y + uy * push)

        new_segments = tuple(LineSegment(pts[k], pts[(k + 1) % n]) for k in range(n))
        new_paths.append(Path(new_segments, closed=True))
        actions.append(
            f"widened narrow neck from {distance:.4g}mm toward {rule_set.min_bridge_width_mm}mm"
        )
    return CompoundPath(tuple(new_paths)), actions


def repair_manufacturing(shape, rule_set: RuleSet) -> ManufacturingRepairResult:
    """Composed pipeline, fixed order: holes/islands cleanup first (so
    later geometric repairs operate on a already-simplified compound),
    then corner rounding, then bridge widening.
    """
    from core.engines.geometry.model import as_compound

    original = as_compound(shape)
    current = original
    actions: list[str] = []

    current, a1 = remove_tiny_holes(current, rule_set)
    actions.extend(a1)
    current, a2 = merge_tiny_islands(current, rule_set)
    actions.extend(a2)
    current, a3 = round_sharp_corners(current, rule_set)
    actions.extend(a3)
    current, a4 = widen_weak_bridges(current, rule_set)
    actions.extend(a4)

    similarity = _similarity_score(original, current, rule_set.flatten_tolerance_mm)
    return ManufacturingRepairResult(current, tuple(actions), similarity)
