"""Deterministic geometry repair — every function here is a pure,
fixed-rule transformation (no scoring, no AI, no "best guess"). Each
takes a Path and returns a new Path plus a list of the actions it took,
so callers get an audit trail (mirrors the RepairResult.actions[]
pattern already established for the eventual Automatic Repair Engine).
"""
from __future__ import annotations

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
from core.engines.geometry.winding import Orientation, orientation


@dataclass(frozen=True)
class RepairResult:
    path: Path
    actions: tuple[str, ...]


def _round_point(p: Point, decimals: int) -> Point:
    return Point(round(p.x, decimals), round(p.y, decimals))


def normalize_coordinate_precision(path: Path, decimals: int = 6) -> RepairResult:
    """Round every coordinate to `decimals` places — numerical hygiene
    against accumulated float error from repeated transforms/imports.
    """

    def round_segment(s: Segment) -> Segment:
        if isinstance(s, LineSegment):
            return LineSegment(_round_point(s.start, decimals), _round_point(s.end, decimals))
        if isinstance(s, BezierSegment):
            return BezierSegment(
                _round_point(s.start, decimals),
                _round_point(s.control1, decimals),
                _round_point(s.control2, decimals),
                _round_point(s.end, decimals),
            )
        if isinstance(s, ArcSegment):
            return ArcSegment(
                _round_point(s.start, decimals),
                _round_point(s.end, decimals),
                _round_point(s.center, decimals),
                round(s.radius, decimals),
                s.clockwise,
            )
        raise TypeError(f"Unknown segment type: {type(s)}")

    new_segments = tuple(round_segment(s) for s in path.segments)
    changed = new_segments != path.segments
    actions = (f"normalized coordinate precision to {decimals} decimals",) if changed else ()
    return RepairResult(Path(new_segments, closed=path.closed), actions)


def remove_zero_length_segments(path: Path, tolerance: float = 1e-6) -> RepairResult:
    kept = [s for s in path.segments if s.start.distance_to(s.end) > tolerance]
    removed = len(path.segments) - len(kept)
    actions = (f"removed {removed} zero-length segment(s)",) if removed else ()
    return RepairResult(Path(tuple(kept), closed=path.closed), actions)


def remove_duplicate_nodes(path: Path, tolerance: float = 1e-6) -> RepairResult:
    """Drops a segment whose start duplicates the previous segment's end
    AND whose own start==end (a degenerate zero-length artifact left by,
    e.g., a naive import) — distinct from `remove_zero_length_segments`
    in that this specifically targets duplicate *node* artifacts at
    segment joins, not just any short segment.
    """
    if not path.segments:
        return RepairResult(path, ())
    kept: list[Segment] = [path.segments[0]]
    removed = 0
    for seg in path.segments[1:]:
        prev_end = kept[-1].end
        if (
            seg.start.distance_to(prev_end) <= tolerance
            and seg.start.distance_to(seg.end) <= tolerance
        ):
            removed += 1
            continue
        kept.append(seg)
    actions = (f"removed {removed} duplicate node artifact(s)",) if removed else ()
    return RepairResult(Path(tuple(kept), closed=path.closed), actions)


def close_tiny_gaps(path: Path, tolerance: float = 0.01) -> RepairResult:
    """If a path is marked closed but its start/end gap is small (likely
    float drift or an incomplete trace, not a genuinely open shape),
    snap the last segment's end to the first segment's start.
    """
    if not path.closed or not path.segments:
        return RepairResult(path, ())
    gap = path.segments[-1].end.distance_to(path.segments[0].start)
    if gap == 0 or gap > tolerance:
        return RepairResult(path, ())

    last = path.segments[-1]
    target = path.segments[0].start
    fixed_last: Segment
    if isinstance(last, LineSegment):
        fixed_last = LineSegment(last.start, target)
    elif isinstance(last, BezierSegment):
        fixed_last = BezierSegment(last.start, last.control1, last.control2, target)
    elif isinstance(last, ArcSegment):
        fixed_last = ArcSegment(last.start, target, last.center, last.radius, last.clockwise)
    else:
        raise TypeError(f"Unknown segment type: {type(last)}")

    new_segments = path.segments[:-1] + (fixed_last,)
    return RepairResult(
        Path(new_segments, closed=True), (f"closed a {gap:.6g}-unit gap at path start/end",)
    )


def _reverse_segment(s: Segment) -> Segment:
    if isinstance(s, LineSegment):
        return LineSegment(s.end, s.start)
    if isinstance(s, BezierSegment):
        return BezierSegment(s.end, s.control2, s.control1, s.start)
    if isinstance(s, ArcSegment):
        return ArcSegment(s.end, s.start, s.center, s.radius, not s.clockwise)
    raise TypeError(f"Unknown segment type: {type(s)}")


def normalize_winding(
    path: Path, target: Orientation = Orientation.COUNTER_CLOCKWISE
) -> RepairResult:
    """Reverses segment order/direction if the path's current winding
    doesn't match `target`. No-op for open paths or degenerate (zero-
    area) paths, where "winding" isn't a meaningful concept to normalize.
    """
    from core.engines.geometry.flatten import flatten_path

    if not path.closed or not path.segments:
        return RepairResult(path, ())
    flat = flatten_path(path)
    ring = flat[:-1] if len(flat) > 1 and flat[0] == flat[-1] else flat
    current = orientation(ring)
    if current in (Orientation.DEGENERATE, target):
        return RepairResult(path, ())

    reversed_segments = tuple(_reverse_segment(s) for s in reversed(path.segments))
    return RepairResult(
        Path(reversed_segments, closed=path.closed),
        (f"reversed winding from {current.value} to {target.value}",),
    )


def repair_path(
    path: Path,
    *,
    gap_tolerance: float = 0.01,
    zero_length_tolerance: float = 1e-6,
    precision_decimals: int = 6,
    target_winding: Orientation = Orientation.COUNTER_CLOCKWISE,
) -> RepairResult:
    """The composed pipeline (Sprint plan's "repair invalid paths"): runs
    every deterministic repair in a fixed, sensible order and accumulates
    the action log. Order matters: dedupe/zero-length cleanup happens
    before gap-closing and winding normalization, so those later steps
    see already-cleaned geometry.
    """
    actions: list[str] = []
    current = path

    for repair_fn, kwargs in (
        (remove_duplicate_nodes, {"tolerance": zero_length_tolerance}),
        (remove_zero_length_segments, {"tolerance": zero_length_tolerance}),
        (close_tiny_gaps, {"tolerance": gap_tolerance}),
        (normalize_winding, {"target": target_winding}),
        (normalize_coordinate_precision, {"decimals": precision_decimals}),
    ):
        result = repair_fn(current, **kwargs)
        current = result.path
        actions.extend(result.actions)

    return RepairResult(current, tuple(actions))


def repair_compound(compound: CompoundPath, **kwargs) -> tuple[RepairResult, ...]:
    return tuple(repair_path(p, **kwargs) for p in compound.paths)


def repair_geometry(shape: Shape, **kwargs) -> tuple[CompoundPath, tuple[str, ...]]:
    results = repair_compound(as_compound(shape), **kwargs)
    all_actions = tuple(a for r in results for a in r.actions)
    return CompoundPath(tuple(r.path for r in results)), all_actions
