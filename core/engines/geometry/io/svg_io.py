"""SVG -> Neutral Geometry importer.

    SVG
     |
Geometry Engine native model (Point/Line/Arc/Bezier/Path/CompoundPath/
Circle/Ellipse/Polygon, Transform -- all reused from
core.engines.geometry, none modified)
     |
shape_to_neutral()  (core.engines.geometry.io.neutral_io, unmodified)
     |
NeutralGeometry

Scope is strictly import: parsing SVG into the existing NeutralGeometry
model. No manufacturing logic, no DXF generation, no preview generation
happens here -- those are separate, already-existing pipeline stages
this module does not call.

Targets SVG as exported by CorelDRAW: <path>, <circle>, <ellipse>,
<rect> (including rounded corners), <polygon>, <polyline>, <line>
elements, nested <g> groups with `transform`, and the root <svg>'s
`width`/`height`/`viewBox` for real-world unit resolution (CorelDRAW's
SVG export can use px, mm, in, or pt depending on export settings, but
NeutralGeometry's `units` field is always "mm" -- see
core/geometry/validator.py -- so every coordinate is converted to true
millimeters here).

Coordinate convention: SVG's Y axis increases downward from the
top-left origin. This importer preserves that convention as-is --
no implicit Y-flip is applied. Changing that convention is an
architectural decision outside this module's scope.

Not supported (out of scope for this import layer, not silently
guessed at): <text> (would require font metrics), <image>, CSS
stylesheets/classes, `<use>`/`<symbol>` references, gradients/patterns,
clipping/masking. These elements are skipped during the tree walk
(their geometry, if any, is not extracted) rather than raising, so a
file that mixes supported and unsupported content still imports the
supported parts.
"""
from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path as FilePath

from core.engines.geometry.io.neutral_io import shape_to_neutral
from core.engines.geometry.model import (
    ArcSegment,
    BezierSegment,
    Circle,
    CompoundPath,
    Ellipse,
    LineSegment,
    Path,
    Point,
    Polygon,
    Segment,
)
from core.engines.geometry.transform import Transform, apply_transform, apply_transform_path, rotate, scale, translate
from core.engines.geometry.validation import IssueType, validate_geometry
from core.exceptions import GeometryFormatException
from core.geometry import NeutralGeometry, geometry_to_dict, validate_geometry_dict_or_raise

# --- Unit resolution ---------------------------------------------------

MM_PER_INCH = 25.4
PX_PER_INCH = 96.0  # CSS/SVG defined pixel density
PT_PER_INCH = 72.0

_UNIT_TO_MM: dict[str, float] = {
    "mm": 1.0,
    "cm": 10.0,
    "in": MM_PER_INCH,
    "pt": MM_PER_INCH / PT_PER_INCH,
    "pc": MM_PER_INCH / 6.0,
    "px": MM_PER_INCH / PX_PER_INCH,
    "": MM_PER_INCH / PX_PER_INCH,  # unitless SVG length defaults to px
}

_LENGTH_RE = re.compile(r"^\s*(-?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)\s*([a-zA-Z%]*)\s*$")


def _parse_length(value: str) -> tuple[float, str]:
    match = _LENGTH_RE.match(value)
    if not match:
        raise GeometryFormatException(f"Could not parse SVG length: {value!r}")
    num_str, unit = match.groups()
    return float(num_str), unit.lower()


def _length_to_mm(value: str) -> float:
    num, unit = _parse_length(value)
    if unit not in _UNIT_TO_MM:
        raise GeometryFormatException(f"Unsupported or ambiguous SVG length unit: {unit!r} in {value!r}")
    return num * _UNIT_TO_MM[unit]


def _parse_viewbox(value: str) -> tuple[float, float, float, float]:
    parts = [float(p) for p in re.split(r"[\s,]+", value.strip()) if p]
    if len(parts) != 4:
        raise GeometryFormatException(f"Invalid SVG viewBox: {value!r}")
    return parts[0], parts[1], parts[2], parts[3]


def _resolve_scale(root: ET.Element) -> float:
    """Millimeters per one SVG user unit, resolved from the root <svg>
    element's width/height and viewBox (standard SVG unit resolution).
    Falls back to 1.0 (user units already treated as mm) only when
    neither width/height nor viewBox is present -- the most
    conservative assumption available, flagged here rather than
    silently picking a different default.
    """
    width_attr = root.get("width")
    viewbox_attr = root.get("viewBox")

    if width_attr and viewbox_attr:
        width_mm = _length_to_mm(width_attr)
        _, _, vb_width, _ = _parse_viewbox(viewbox_attr)
        if vb_width <= 0:
            raise GeometryFormatException("SVG viewBox has non-positive width")
        return width_mm / vb_width

    if width_attr:
        num, unit = _parse_length(width_attr)
        if num <= 0:
            raise GeometryFormatException("SVG root width must be positive")
        if unit not in _UNIT_TO_MM:
            raise GeometryFormatException(
                f"Cannot resolve real-world size from width unit {unit!r}"
            )
        return _UNIT_TO_MM[unit]

    if viewbox_attr:
        return _UNIT_TO_MM[""]

    return 1.0


# --- transform="..." attribute parsing (reuses transform.py primitives) ----


_TRANSFORM_FN_RE = re.compile(r"(\w+)\s*\(([^)]*)\)")


def _parse_transform(value: str) -> Transform:
    result = Transform()
    for name, args_str in _TRANSFORM_FN_RE.findall(value):
        args = [float(a) for a in re.split(r"[\s,]+", args_str.strip()) if a]
        if name == "translate":
            t = translate(args[0], args[1] if len(args) > 1 else 0.0)
        elif name == "scale":
            t = scale(args[0], args[1] if len(args) > 1 else args[0])
        elif name == "rotate":
            angle = math.radians(args[0])
            t = rotate(angle, Point(args[1], args[2])) if len(args) >= 3 else rotate(angle)
        elif name == "matrix":
            if len(args) != 6:
                raise GeometryFormatException(f"matrix() transform needs 6 args, got {len(args)}")
            t = Transform(*args)
        elif name == "skewX":
            t = Transform(a=1, b=0, c=math.tan(math.radians(args[0])), d=1)
        elif name == "skewY":
            t = Transform(a=1, b=math.tan(math.radians(args[0])), c=0, d=1)
        else:
            raise GeometryFormatException(f"Unsupported SVG transform function: {name!r}")
        result = result.then(t)
    return result


# --- path 'd' attribute parsing ---------------------------------------


class _PathDataParser:
    """Character-level parser for the SVG path 'd' attribute. Handles
    packed numbers (e.g. "1.5.5" -> 1.5, 0.5) and packed arc flags
    (e.g. "01" -> flag=0, flag=1), both of which occur in real
    tool-exported SVG and would break a naive regex/split tokenizer.
    """

    _COMMANDS = set("MmZzLlHhVvCcSsQqTtAa")

    def __init__(self, d: str) -> None:
        self._s = d
        self._i = 0
        self._n = len(d)

    def _skip_ws(self) -> None:
        while self._i < self._n and (self._s[self._i].isspace() or self._s[self._i] == ","):
            self._i += 1

    def has_more(self) -> bool:
        self._skip_ws()
        return self._i < self._n

    def peek_command(self) -> str | None:
        self._skip_ws()
        if self._i < self._n and self._s[self._i] in self._COMMANDS:
            return self._s[self._i]
        return None

    def next_command(self) -> str:
        self._skip_ws()
        c = self._s[self._i]
        if c not in self._COMMANDS:
            raise GeometryFormatException(
                f"Expected SVG path command at position {self._i}, got {c!r}"
            )
        self._i += 1
        return c

    def next_number(self) -> float:
        self._skip_ws()
        start = self._i
        if self._i < self._n and self._s[self._i] in "+-":
            self._i += 1
        seen_dot = False
        while self._i < self._n and (
            self._s[self._i].isdigit() or (self._s[self._i] == "." and not seen_dot)
        ):
            if self._s[self._i] == ".":
                seen_dot = True
            self._i += 1
        if self._i < self._n and self._s[self._i] in "eE":
            j = self._i + 1
            if j < self._n and self._s[j] in "+-":
                j += 1
            if j < self._n and self._s[j].isdigit():
                self._i = j
                while self._i < self._n and self._s[self._i].isdigit():
                    self._i += 1
        if self._i == start:
            raise GeometryFormatException(f"Expected a number in SVG path data at position {self._i}")
        return float(self._s[start : self._i])

    def next_flag(self) -> bool:
        self._skip_ws()
        if self._i >= self._n or self._s[self._i] not in "01":
            raise GeometryFormatException(f"Expected an arc flag (0 or 1) at position {self._i}")
        value = self._s[self._i] == "1"
        self._i += 1
        return value


def _quad_to_cubic_controls(start: Point, control: Point, end: Point) -> tuple[Point, Point]:
    """Exact quadratic -> cubic Bezier conversion (standard formula):
    each cubic control point sits 2/3 of the way from its endpoint
    toward the quadratic control point.
    """
    c1 = Point(start.x + 2 / 3 * (control.x - start.x), start.y + 2 / 3 * (control.y - start.y))
    c2 = Point(end.x + 2 / 3 * (control.x - end.x), end.y + 2 / 3 * (control.y - end.y))
    return c1, c2


def _ellipse_arc_to_beziers(
    cx: float, cy: float, rx: float, ry: float, phi: float, theta1: float, delta_theta: float,
    max_span_degrees: float = 90.0,
) -> tuple[BezierSegment, ...]:
    """Parametric-ellipse-plus-tangent Bezier approximation, subdividing
    into spans of at most `max_span_degrees` (same kappa technique as
    core.engines.geometry.flatten.arc_to_beziers, generalized here for
    unequal radii and rotation, which that function doesn't need to
    handle since it only ever approximates circular ArcSegments).
    """
    max_span = math.radians(max_span_degrees)
    steps = max(1, math.ceil(abs(delta_theta) / max_span))
    step_angle = delta_theta / steps
    kappa = 4 / 3 * math.tan(step_angle / 4)
    cos_phi, sin_phi = math.cos(phi), math.sin(phi)

    def point_at(theta: float) -> Point:
        ex, ey = rx * math.cos(theta), ry * math.sin(theta)
        return Point(cx + ex * cos_phi - ey * sin_phi, cy + ex * sin_phi + ey * cos_phi)

    def tangent_at(theta: float) -> tuple[float, float]:
        dx, dy = -rx * math.sin(theta), ry * math.cos(theta)
        return dx * cos_phi - dy * sin_phi, dx * sin_phi + dy * cos_phi

    segments = []
    for i in range(steps):
        a0 = theta1 + step_angle * i
        a1 = theta1 + step_angle * (i + 1)
        p0, p1 = point_at(a0), point_at(a1)
        t0x, t0y = tangent_at(a0)
        t1x, t1y = tangent_at(a1)
        c1 = Point(p0.x + kappa * t0x, p0.y + kappa * t0y)
        c2 = Point(p1.x - kappa * t1x, p1.y - kappa * t1y)
        segments.append(BezierSegment(p0, c1, c2, p1))
    return tuple(segments)


def _svg_arc_to_segments(
    start: Point, rx: float, ry: float, x_axis_rotation_deg: float,
    large_arc: bool, sweep: bool, end: Point,
) -> tuple[Segment, ...]:
    """SVG elliptical arc (A/a) -> native segments, via the standard
    endpoint-to-center parameterization (SVG spec Appendix F.6).
    Degenerate arcs (coincident endpoints or a zero radius) collapse to
    a straight line, per spec F.6.2. Circular, unrotated arcs become an
    exact ArcSegment; true (rotated and/or rx != ry) ellipse arcs are
    approximated with cubic Beziers.
    """
    if start == end:
        return ()
    rx, ry = abs(rx), abs(ry)
    if rx == 0 or ry == 0:
        return (LineSegment(start, end),)

    phi = math.radians(x_axis_rotation_deg % 360)
    cos_phi, sin_phi = math.cos(phi), math.sin(phi)

    dx2, dy2 = (start.x - end.x) / 2, (start.y - end.y) / 2
    x1p = cos_phi * dx2 + sin_phi * dy2
    y1p = -sin_phi * dx2 + cos_phi * dy2

    lam = (x1p**2) / (rx**2) + (y1p**2) / (ry**2)
    if lam > 1:
        scale_r = math.sqrt(lam)
        rx *= scale_r
        ry *= scale_r

    sign = -1.0 if large_arc == sweep else 1.0
    num = (rx**2) * (ry**2) - (rx**2) * (y1p**2) - (ry**2) * (x1p**2)
    den = (rx**2) * (y1p**2) + (ry**2) * (x1p**2)
    coef = sign * math.sqrt(max(0.0, num / den)) if den != 0 else 0.0
    cxp = coef * (rx * y1p / ry)
    cyp = coef * -(ry * x1p / rx)

    cx = cos_phi * cxp - sin_phi * cyp + (start.x + end.x) / 2
    cy = sin_phi * cxp + cos_phi * cyp + (start.y + end.y) / 2

    def angle(ux: float, uy: float, vx: float, vy: float) -> float:
        dot = ux * vx + uy * vy
        length = math.hypot(ux, uy) * math.hypot(vx, vy)
        a = math.acos(max(-1.0, min(1.0, dot / length))) if length else 0.0
        return a if (ux * vy - uy * vx) >= 0 else -a

    theta1 = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    delta_theta = angle((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and delta_theta > 0:
        delta_theta -= 2 * math.pi
    elif sweep and delta_theta < 0:
        delta_theta += 2 * math.pi

    if abs(rx - ry) < 1e-9 and abs(phi) < 1e-9:
        center = Point(cx, cy)
        return (ArcSegment(start, end, center, rx, clockwise=delta_theta < 0),)

    return _ellipse_arc_to_beziers(cx, cy, rx, ry, phi, theta1, delta_theta)


def _parse_path_d(d: str) -> tuple[Path, ...]:
    """A single 'd' attribute can contain multiple M-started subpaths;
    returns one Path per subpath.
    """
    parser = _PathDataParser(d)
    paths: list[Path] = []
    segments: list[Segment] = []
    current = Point(0.0, 0.0)
    subpath_start = current
    last_cubic_control: Point | None = None
    last_quad_control: Point | None = None
    last_command: str | None = None

    def flush_subpath(closed: bool) -> None:
        nonlocal segments
        if segments:
            paths.append(Path(tuple(segments), closed=closed))
        segments = []

    while parser.has_more():
        cmd = parser.peek_command()
        if cmd is None:
            if last_command is None:
                raise GeometryFormatException("SVG path data starts without a command")
            cmd = last_command
        else:
            parser.next_command()

        is_relative = cmd.islower()
        upper = cmd.upper()

        if upper == "M":
            flush_subpath(closed=False)
            x, y = parser.next_number(), parser.next_number()
            current = Point(current.x + x, current.y + y) if is_relative else Point(x, y)
            subpath_start = current
            last_cubic_control = last_quad_control = None
            last_command = "l" if is_relative else "L"  # implicit repeats of M are L
            continue

        if upper == "Z":
            if segments:
                last_end = segments[-1].end
                if last_end != subpath_start:
                    segments.append(LineSegment(last_end, subpath_start))
            flush_subpath(closed=True)
            current = subpath_start
            last_cubic_control = last_quad_control = None
            last_command = cmd
            continue

        if upper == "L":
            x, y = parser.next_number(), parser.next_number()
            end = Point(current.x + x, current.y + y) if is_relative else Point(x, y)
            segments.append(LineSegment(current, end))
            current = end
            last_cubic_control = last_quad_control = None

        elif upper == "H":
            x = parser.next_number()
            end = Point(current.x + x, current.y) if is_relative else Point(x, current.y)
            segments.append(LineSegment(current, end))
            current = end
            last_cubic_control = last_quad_control = None

        elif upper == "V":
            y = parser.next_number()
            end = Point(current.x, current.y + y) if is_relative else Point(current.x, y)
            segments.append(LineSegment(current, end))
            current = end
            last_cubic_control = last_quad_control = None

        elif upper == "C":
            x1, y1 = parser.next_number(), parser.next_number()
            x2, y2 = parser.next_number(), parser.next_number()
            x, y = parser.next_number(), parser.next_number()
            if is_relative:
                c1 = Point(current.x + x1, current.y + y1)
                c2 = Point(current.x + x2, current.y + y2)
                end = Point(current.x + x, current.y + y)
            else:
                c1, c2, end = Point(x1, y1), Point(x2, y2), Point(x, y)
            segments.append(BezierSegment(current, c1, c2, end))
            current = end
            last_cubic_control, last_quad_control = c2, None

        elif upper == "S":
            x2, y2 = parser.next_number(), parser.next_number()
            x, y = parser.next_number(), parser.next_number()
            if is_relative:
                c2 = Point(current.x + x2, current.y + y2)
                end = Point(current.x + x, current.y + y)
            else:
                c2, end = Point(x2, y2), Point(x, y)
            c1 = (
                Point(2 * current.x - last_cubic_control.x, 2 * current.y - last_cubic_control.y)
                if last_cubic_control is not None
                else current
            )
            segments.append(BezierSegment(current, c1, c2, end))
            current = end
            last_cubic_control, last_quad_control = c2, None

        elif upper == "Q":
            x1, y1 = parser.next_number(), parser.next_number()
            x, y = parser.next_number(), parser.next_number()
            if is_relative:
                qc = Point(current.x + x1, current.y + y1)
                end = Point(current.x + x, current.y + y)
            else:
                qc, end = Point(x1, y1), Point(x, y)
            c1, c2 = _quad_to_cubic_controls(current, qc, end)
            segments.append(BezierSegment(current, c1, c2, end))
            current = end
            last_quad_control, last_cubic_control = qc, None

        elif upper == "T":
            x, y = parser.next_number(), parser.next_number()
            end = Point(current.x + x, current.y + y) if is_relative else Point(x, y)
            qc = (
                Point(2 * current.x - last_quad_control.x, 2 * current.y - last_quad_control.y)
                if last_quad_control is not None
                else current
            )
            c1, c2 = _quad_to_cubic_controls(current, qc, end)
            segments.append(BezierSegment(current, c1, c2, end))
            current = end
            last_quad_control, last_cubic_control = qc, None

        elif upper == "A":
            rx = parser.next_number()
            ry = parser.next_number()
            x_rotation = parser.next_number()
            large_arc = parser.next_flag()
            sweep = parser.next_flag()
            x, y = parser.next_number(), parser.next_number()
            end = Point(current.x + x, current.y + y) if is_relative else Point(x, y)
            segments.extend(_svg_arc_to_segments(current, rx, ry, x_rotation, large_arc, sweep, end))
            current = end
            last_cubic_control = last_quad_control = None

        else:
            raise GeometryFormatException(f"Unsupported SVG path command: {cmd!r}")

        last_command = cmd

    flush_subpath(closed=False)
    return tuple(paths)


# --- element parsers -----------------------------------------------------


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _parse_points_attr(value: str) -> tuple[Point, ...]:
    nums = [float(n) for n in re.split(r"[\s,]+", value.strip()) if n]
    if len(nums) % 2 != 0:
        raise GeometryFormatException(f"SVG points attribute has an odd number of values: {value!r}")
    return tuple(Point(nums[i], nums[i + 1]) for i in range(0, len(nums), 2))


def _parse_rect_element(el: ET.Element) -> Path:
    x = float(el.get("x", "0"))
    y = float(el.get("y", "0"))
    w = float(el.get("width", "0"))
    h = float(el.get("height", "0"))
    if w <= 0 or h <= 0:
        raise GeometryFormatException("SVG <rect> must have positive width and height")

    rx_raw, ry_raw = el.get("rx"), el.get("ry")
    if rx_raw is None and ry_raw is None:
        rx = ry = 0.0
    else:
        rx = float(rx_raw) if rx_raw is not None else float(ry_raw)  # type: ignore[arg-type]
        ry = float(ry_raw) if ry_raw is not None else float(rx_raw)  # type: ignore[arg-type]
    rx, ry = min(rx, w / 2), min(ry, h / 2)

    if rx <= 0 or ry <= 0:
        points = (Point(x, y), Point(x + w, y), Point(x + w, y + h), Point(x, y + h))
        return Polygon(points, closed=True).to_path()

    p1, p2 = Point(x + rx, y), Point(x + w - rx, y)
    p3, p4 = Point(x + w, y + ry), Point(x + w, y + h - ry)
    p5, p6 = Point(x + w - rx, y + h), Point(x + rx, y + h)
    p7, p8 = Point(x, y + h - ry), Point(x, y + ry)

    segments: list[Segment] = [LineSegment(p1, p2)]
    segments.extend(_svg_arc_to_segments(p2, rx, ry, 0, False, True, p3))
    segments.append(LineSegment(p3, p4))
    segments.extend(_svg_arc_to_segments(p4, rx, ry, 0, False, True, p5))
    segments.append(LineSegment(p5, p6))
    segments.extend(_svg_arc_to_segments(p6, rx, ry, 0, False, True, p7))
    segments.append(LineSegment(p7, p8))
    segments.extend(_svg_arc_to_segments(p8, rx, ry, 0, False, True, p1))
    return Path(tuple(segments), closed=True)


def _walk(element: ET.Element, inherited: Transform, output: list[Path]) -> None:
    tag = _strip_ns(element.tag)

    local_transform = inherited
    transform_attr = element.get("transform")
    if transform_attr:
        local_transform = inherited.then(_parse_transform(transform_attr))

    if tag in ("g", "svg", "a"):
        for child in element:
            _walk(child, local_transform, output)
        return

    if tag == "path":
        d = element.get("d")
        if d:
            for subpath in _parse_path_d(d):
                output.append(apply_transform_path(subpath, local_transform))
        return

    if tag == "circle":
        cx, cy, r = float(element.get("cx", "0")), float(element.get("cy", "0")), float(element.get("r", "0"))
        if r <= 0:
            raise GeometryFormatException("SVG <circle> must have r > 0")
        output.append(apply_transform_path(Circle(Point(cx, cy), r).to_path(), local_transform))
        return

    if tag == "ellipse":
        cx, cy = float(element.get("cx", "0")), float(element.get("cy", "0"))
        rx, ry = float(element.get("rx", "0")), float(element.get("ry", "0"))
        if rx <= 0 or ry <= 0:
            raise GeometryFormatException("SVG <ellipse> must have rx > 0 and ry > 0")
        output.append(apply_transform_path(Ellipse(Point(cx, cy), rx, ry).to_path(), local_transform))
        return

    if tag == "rect":
        output.append(apply_transform_path(_parse_rect_element(element), local_transform))
        return

    if tag == "polygon":
        points = _parse_points_attr(element.get("points", ""))
        if len(points) < 3:
            raise GeometryFormatException("SVG <polygon> needs at least 3 points")
        output.append(
            apply_transform_path(Polygon(points, closed=True).to_path(), local_transform)
        )
        return

    if tag == "polyline":
        points = _parse_points_attr(element.get("points", ""))
        if len(points) < 2:
            raise GeometryFormatException("SVG <polyline> needs at least 2 points")
        segs = tuple(LineSegment(points[i], points[i + 1]) for i in range(len(points) - 1))
        output.append(apply_transform_path(Path(segs, closed=False), local_transform))
        return

    if tag == "line":
        p1 = Point(float(element.get("x1", "0")), float(element.get("y1", "0")))
        p2 = Point(float(element.get("x2", "0")), float(element.get("y2", "0")))
        output.append(apply_transform_path(Path((LineSegment(p1, p2),), closed=False), local_transform))
        return

    # Unsupported element (text, image, defs, style, ...): skip its own
    # geometry but still walk children, in case a supported element is
    # nested inside an otherwise-ignored container.
    for child in element:
        _walk(child, local_transform, output)


# --- public API ------------------------------------------------------------


def parse_svg_string(svg_text: str) -> CompoundPath:
    """SVG text -> the Geometry Engine's native CompoundPath. Pure
    parsing; no validation performed here (see svg_to_neutral for the
    validated, NeutralGeometry-producing entry point).
    """
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        raise GeometryFormatException(f"Malformed SVG/XML: {exc}") from exc

    if _strip_ns(root.tag) != "svg":
        raise GeometryFormatException(f"Root element is not <svg>: <{_strip_ns(root.tag)}>")

    scale_mm = _resolve_scale(root)

    output: list[Path] = []
    root_transform = Transform()
    transform_attr = root.get("transform")
    if transform_attr:
        root_transform = _parse_transform(transform_attr)
    for child in root:
        _walk(child, root_transform, output)

    if not output:
        raise GeometryFormatException("SVG contains no supported geometry elements")

    return apply_transform(CompoundPath(tuple(output)), scale(scale_mm))


def parse_svg_file(path: str | FilePath) -> CompoundPath:
    text = FilePath(path).read_text(encoding="utf-8")
    return parse_svg_string(text)


# Structural issue types that indicate a genuine parsing/data defect and
# should block the import outright. Everything else (open curves,
# self-intersections, thin/duplicate segments, degenerate winding) is
# valid SVG content that later pipeline stages (Geometry/Manufacturing
# validation, already existing and unmodified) are responsible for
# judging -- this importer's job is faithful conversion, not
# manufacturability.
_BLOCKING_ISSUE_TYPES = frozenset({IssueType.INVALID_COORDINATES, IssueType.CORRUPT_GEOMETRY})


def svg_to_neutral(
    svg_text: str, source_adapter: str = "svg_import", source_file_hint: str | None = None
) -> NeutralGeometry:
    """SVG text -> NeutralGeometry. Reuses, unmodified:
      - core.engines.geometry.validation.validate_geometry (structural
        check on the native model)
      - core.engines.geometry.io.neutral_io.shape_to_neutral (the
        engine-model -> wire-format bridge)
      - core.geometry.validator.validate_geometry_dict_or_raise (the
        wire-format schema check)
    """
    compound = parse_svg_string(svg_text)

    issues = validate_geometry(compound)
    blocking = [i for i in issues if i.issue_type in _BLOCKING_ISSUE_TYPES]
    if blocking:
        raise GeometryFormatException(
            "Imported SVG geometry failed structural validation",
            context={"issues": [i.detail for i in blocking]},
        )

    geometry = shape_to_neutral(compound, source_adapter=source_adapter)
    if source_file_hint:
        geometry = replace(
            geometry, metadata=replace(geometry.metadata, source_file_hint=source_file_hint)
        )

    validate_geometry_dict_or_raise(geometry_to_dict(geometry))
    return geometry


def svg_file_to_neutral(path: str | FilePath, source_adapter: str = "svg_import") -> NeutralGeometry:
    text = FilePath(path).read_text(encoding="utf-8")
    return svg_to_neutral(text, source_adapter=source_adapter, source_file_hint=str(path))
