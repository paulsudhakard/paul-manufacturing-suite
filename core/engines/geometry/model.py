"""Geometry Engine primitive model.

Design: every primitive (Circle, Ellipse, Polygon) reduces to a canonical
`Path`/`CompoundPath` of typed segments (Line/Arc/Bezier) via `.to_path()`.
Every other module in this engine (measure, offset, validation, repair,
boolean_prep) operates on that canonical form — this is what "avoid
duplicated geometry logic" (the engineering requirement) means in
practice: one code path per algorithm, not one per primitive type.

All types are immutable (frozen dataclasses / tuples throughout), per
the engineering requirement.

Note on scope: `ArcSegment` is a *circular* arc (constant radius) only.
General elliptical arcs (SVG's arc command with rx != ry) are supported
on import by approximating with cubic Beziers — see io/svg_io.py — so
that this module's arc math (bounding box, offset, length) stays exact
rather than silently approximate.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def distance_to(self, other: "Point") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


@dataclass(frozen=True)
class LineSegment:
    start: Point
    end: Point


@dataclass(frozen=True)
class ArcSegment:
    """A circular arc from `start` to `end`, centered at `center`, with
    the given `radius`. `clockwise` gives the sweep direction. Callers
    are responsible for constructing geometrically consistent arcs
    (|start - center| ~= |end - center| ~= radius); `validation.py`
    checks this on imported/user-supplied data.
    """

    start: Point
    end: Point
    center: Point
    radius: float
    clockwise: bool

    def start_angle(self) -> float:
        return math.atan2(self.start.y - self.center.y, self.start.x - self.center.x)

    def end_angle(self) -> float:
        return math.atan2(self.end.y - self.center.y, self.end.x - self.center.x)

    def sweep_angle(self) -> float:
        """Signed sweep in radians, positive = counter-clockwise, matching
        `clockwise` for direction. Always in (-2*pi, 2*pi].
        """
        start_a, end_a = self.start_angle(), self.end_angle()
        if self.clockwise:
            delta = start_a - end_a
        else:
            delta = end_a - start_a
        while delta < 0:
            delta += 2 * math.pi
        if delta == 0:
            delta = 2 * math.pi  # full circle expressed as a degenerate start==end arc
        return -delta if self.clockwise else delta


@dataclass(frozen=True)
class BezierSegment:
    """Cubic Bezier: start, two control points, end."""

    start: Point
    control1: Point
    control2: Point
    end: Point

    def point_at(self, t: float) -> Point:
        mt = 1 - t
        x = (
            mt**3 * self.start.x
            + 3 * mt**2 * t * self.control1.x
            + 3 * mt * t**2 * self.control2.x
            + t**3 * self.end.x
        )
        y = (
            mt**3 * self.start.y
            + 3 * mt**2 * t * self.control1.y
            + 3 * mt * t**2 * self.control2.y
            + t**3 * self.end.y
        )
        return Point(x, y)


Segment = LineSegment | ArcSegment | BezierSegment


def segment_start(segment: Segment) -> Point:
    return segment.start


def segment_end(segment: Segment) -> Point:
    return segment.end


@dataclass(frozen=True)
class Path:
    """A single subpath: an ordered, (ideally) contiguous chain of
    segments. `closed` declares intent (should segments[-1].end coincide
    with segments[0].start); `validation.py` checks whether reality
    matches that intent rather than assuming it.
    """

    segments: tuple[Segment, ...]
    closed: bool = False

    def to_path(self) -> "Path":
        return self


@dataclass(frozen=True)
class CompoundPath:
    """Multiple subpaths sharing one logical shape (e.g. a ring: an outer
    Path plus an inner hole Path with opposite winding).
    """

    paths: tuple[Path, ...]

    def to_path(self) -> "CompoundPath":
        return self


@dataclass(frozen=True)
class Circle:
    center: Point
    radius: float

    def to_path(self) -> Path:
        """Four quarter-circle arcs, counter-clockwise from angle 0."""
        cx, cy, r = self.center.x, self.center.y, self.radius
        pts = [Point(cx + r, cy), Point(cx, cy + r), Point(cx - r, cy), Point(cx, cy - r)]
        segments = tuple(
            ArcSegment(pts[i], pts[(i + 1) % 4], self.center, r, clockwise=False) for i in range(4)
        )
        return Path(segments, closed=True)


@dataclass(frozen=True)
class Ellipse:
    center: Point
    rx: float
    ry: float
    rotation: float = 0.0  # radians, about center

    def to_path(self) -> Path:
        """Four cubic-Bezier quadrants (the standard kappa=0.5522847498
        approximation) — ellipses have no exact representation via
        circular arcs, so unlike Circle this is a (very close, ~0.02%
        max radial error) approximation, not exact.
        """
        k = 0.5522847498307936
        cx, cy = self.center.x, self.center.y
        rx, ry = self.rx, self.ry

        def local(x: float, y: float) -> Point:
            cos_r, sin_r = math.cos(self.rotation), math.sin(self.rotation)
            return Point(cx + x * cos_r - y * sin_r, cy + x * sin_r + y * cos_r)

        p0, p1, p2, p3 = local(rx, 0), local(0, ry), local(-rx, 0), local(0, -ry)
        c = [
            (local(rx, k * ry), local(k * rx, ry)),
            (local(-k * rx, ry), local(-rx, k * ry)),
            (local(-rx, -k * ry), local(-k * rx, -ry)),
            (local(k * rx, -ry), local(rx, -k * ry)),
        ]
        pts = [p0, p1, p2, p3]
        segments = tuple(
            BezierSegment(pts[i], c[i][0], c[i][1], pts[(i + 1) % 4]) for i in range(4)
        )
        return Path(segments, closed=True)


@dataclass(frozen=True)
class Polygon:
    points: tuple[Point, ...]
    closed: bool = True

    def to_path(self) -> Path:
        n = len(self.points)
        pairs = [
            (self.points[i], self.points[(i + 1) % n]) for i in range(n if self.closed else n - 1)
        ]
        segments = tuple(LineSegment(a, b) for a, b in pairs)
        return Path(segments, closed=self.closed)


Shape = Circle | Ellipse | Polygon | Path | CompoundPath


def as_compound(shape: Shape) -> CompoundPath:
    """Normalize any Shape to a CompoundPath (of one or more Paths) —
    the common form most algorithms below iterate over.
    """
    path_or_compound = shape.to_path()
    if isinstance(path_or_compound, CompoundPath):
        return path_or_compound
    return CompoundPath((path_or_compound,))
