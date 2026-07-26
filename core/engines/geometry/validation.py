"""Structural geometry validation — deliberately *not* the Manufacturing
Geometry Validation Engine's defect checklist (bridge width, wall
thickness, etc. — those require manufacturing-rule context this engine
doesn't have and isn't meant to). This module only answers: "is this
geometry structurally sound enough to operate on?" — open curves,
NaN/Inf coordinates, duplicate/zero-length segments, self-intersections,
invalid winding, discontinuous (corrupt) paths, disconnected chains.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from core.engines.geometry.boolean_prep import find_intersections
from core.engines.geometry.flatten import DEFAULT_TOLERANCE_MM, flatten_path
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
from core.engines.geometry.winding import Orientation, orientation

COORDINATE_EPSILON = 1e-9


class IssueType(Enum):
    OPEN_CURVE = "open_curve"
    INVALID_COORDINATES = "invalid_coordinates"
    DUPLICATE_CONSECUTIVE_NODES = "duplicate_consecutive_nodes"
    ZERO_LENGTH_SEGMENT = "zero_length_segment"
    SELF_INTERSECTION = "self_intersection"
    INVALID_WINDING = "invalid_winding"
    CORRUPT_GEOMETRY = "corrupt_geometry"
    DISCONNECTED_GEOMETRY = "disconnected_geometry"


@dataclass(frozen=True)
class GeometryIssue:
    issue_type: IssueType
    path_index: int
    detail: str
    segment_index: int | None = None


def _points_of_segment(segment: Segment) -> tuple[Point, ...]:
    if isinstance(segment, LineSegment):
        return (segment.start, segment.end)
    if isinstance(segment, ArcSegment):
        return (segment.start, segment.end, segment.center)
    if isinstance(segment, BezierSegment):
        return (segment.start, segment.control1, segment.control2, segment.end)
    return ()


def _is_finite_point(p: Point) -> bool:
    return math.isfinite(p.x) and math.isfinite(p.y)


def validate_path(
    path: Path, path_index: int, tolerance: float = DEFAULT_TOLERANCE_MM
) -> list[GeometryIssue]:
    issues: list[GeometryIssue] = []

    if not path.segments:
        issues.append(
            GeometryIssue(IssueType.CORRUPT_GEOMETRY, path_index, "Path has no segments")
        )
        return issues

    # Invalid coordinates (NaN/Inf) and zero-length segments.
    for seg_index, segment in enumerate(path.segments):
        for p in _points_of_segment(segment):
            if not _is_finite_point(p):
                issues.append(
                    GeometryIssue(
                        IssueType.INVALID_COORDINATES,
                        path_index,
                        f"Non-finite coordinate: ({p.x}, {p.y})",
                        seg_index,
                    )
                )
        length = segment.start.distance_to(segment.end)
        if math.isfinite(length) and length <= tolerance:
            issues.append(
                GeometryIssue(
                    IssueType.ZERO_LENGTH_SEGMENT,
                    path_index,
                    f"Segment {seg_index} has near-zero length ({length:.6g})",
                    seg_index,
                )
            )

    # Discontinuous / corrupt: each segment's end must meet the next
    # segment's start (this is what "disconnected geometry" means at the
    # single-path level — a compound path's separate subpaths are
    # normal, e.g. holes, and aren't flagged here).
    for i in range(len(path.segments) - 1):
        gap = path.segments[i].end.distance_to(path.segments[i + 1].start)
        if gap > tolerance:
            issues.append(
                GeometryIssue(
                    IssueType.DISCONNECTED_GEOMETRY,
                    path_index,
                    f"Gap of {gap:.6g} between segment {i} end and segment {i + 1} start",
                    i,
                )
            )

    # Open curve: closed=True should mean segments[-1].end == segments[0].start.
    if path.closed:
        gap = path.segments[-1].end.distance_to(path.segments[0].start)
        if gap > tolerance:
            issues.append(
                GeometryIssue(
                    IssueType.OPEN_CURVE,
                    path_index,
                    f"Path marked closed but start/end gap is {gap:.6g}",
                )
            )
    else:
        issues.append(
            GeometryIssue(IssueType.OPEN_CURVE, path_index, "Path is open (closed=False)")
        )

    # Duplicate consecutive nodes + self-intersection, via the flattened polyline.
    try:
        flat = flatten_path(path, tolerance)
    except Exception as exc:  # pragma: no cover - defensive; flatten_* raise TypeError only
        issues.append(
            GeometryIssue(IssueType.CORRUPT_GEOMETRY, path_index, f"Could not flatten: {exc}")
        )
        return issues

    for i in range(len(flat) - 1):
        if flat[i].distance_to(flat[i + 1]) <= COORDINATE_EPSILON:
            issues.append(
                GeometryIssue(
                    IssueType.DUPLICATE_CONSECUTIVE_NODES,
                    path_index,
                    f"Duplicate consecutive node at index {i}: {flat[i]}",
                )
            )

    if path.closed and len(flat) >= 3:
        ring = flat[:-1] if flat[0] == flat[-1] else flat
        if orientation(ring) == Orientation.DEGENERATE:
            issues.append(
                GeometryIssue(
                    IssueType.INVALID_WINDING,
                    path_index,
                    "Path has zero signed area (degenerate winding)",
                )
            )
        n = len(ring)
        self_intersections = find_intersections(ring, ring)
        # Adjacent-edge shared endpoints always "intersect" trivially;
        # only report intersections between genuinely non-adjacent edges.
        real = [
            x
            for x in self_intersections
            if abs(x.subject_edge_index - x.clip_edge_index) % n not in (0, 1, n - 1)
        ]
        if real:
            issues.append(
                GeometryIssue(
                    IssueType.SELF_INTERSECTION,
                    path_index,
                    f"{len(real)} self-intersection(s) found",
                )
            )

    return issues


def validate_compound(
    compound: CompoundPath, tolerance: float = DEFAULT_TOLERANCE_MM
) -> list[GeometryIssue]:
    issues: list[GeometryIssue] = []
    for i, path in enumerate(compound.paths):
        issues.extend(validate_path(path, i, tolerance))
    return issues


def validate_geometry(shape: Shape, tolerance: float = DEFAULT_TOLERANCE_MM) -> list[GeometryIssue]:
    return validate_compound(as_compound(shape), tolerance)
