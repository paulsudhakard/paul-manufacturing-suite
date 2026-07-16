"""Synthetic regression fixtures, standing in for real production
artwork until real logos are supplied (per the growing-regression-suite
requirement). Every fixture here is generic, parametric geometry
representative of a *structural category* (nested borders, dense detail,
tiny text, a star, a wreath-like arrangement, a signature-like open
curve) — none reproduce any specific real seal, logo, or trademark.

When real customer artwork is supplied and exposes a bug, add it here
(imported from its actual file) alongside these, per the engineering
rule: fix the generic algorithm, then pin the failing artwork as a
permanent regression fixture.
"""

from __future__ import annotations

import math

from core.engines.geometry.model import Circle, CompoundPath, Point, Polygon


def _ring_points(cx: float, cy: float, r: float, n: int = 48) -> tuple[Point, ...]:
    return tuple(
        Point(cx + r * math.cos(2 * math.pi * i / n), cy + r * math.sin(2 * math.pi * i / n))
        for i in range(n)
    )


def corporate_seal() -> CompoundPath:
    """Outer circle + a single inner ring border (hole, opposite winding)."""
    outer = Circle(Point(0, 0), 25).to_path()
    inner_border = Polygon(tuple(reversed(_ring_points(0, 0, 20)))).to_path()
    return CompoundPath((outer, inner_border))


def doctor_seal() -> CompoundPath:
    """Double nested ring border, common on professional/medical seals."""
    outer = Circle(Point(0, 0), 25).to_path()
    ring1 = Polygon(tuple(reversed(_ring_points(0, 0, 21)))).to_path()
    ring2 = Circle(Point(0, 0), 19).to_path()
    ring3 = Polygon(tuple(reversed(_ring_points(0, 0, 15)))).to_path()
    return CompoundPath((outer, ring1, ring2, ring3))


def _cross_polygon(cx: float, cy: float, size: float, thickness: float) -> Polygon:
    h = thickness / 2
    s = size / 2
    return Polygon(
        (
            Point(cx - h, cy - s),
            Point(cx + h, cy - s),
            Point(cx + h, cy - h),
            Point(cx + s, cy - h),
            Point(cx + s, cy + h),
            Point(cx + h, cy + h),
            Point(cx + h, cy + s),
            Point(cx - h, cy + s),
            Point(cx - h, cy + h),
            Point(cx - s, cy + h),
            Point(cx - s, cy - h),
            Point(cx - h, cy - h),
        )
    )


def hospital_seal() -> CompoundPath:
    outer = Circle(Point(0, 0), 25).to_path()
    cross = _cross_polygon(0, 0, 16, 5).to_path()
    return CompoundPath((outer, cross))


def church_seal() -> CompoundPath:
    outer = Circle(Point(0, 0), 25).to_path()
    cross = _cross_polygon(0, 2, 20, 4).to_path()
    return CompoundPath((outer, cross))


def architect_seal() -> CompoundPath:
    outer = Circle(Point(0, 0), 25).to_path()
    triangle = Polygon((Point(0, 14), Point(-12, -8), Point(12, -8))).to_path()
    return CompoundPath((outer, triangle))


def lawyer_seal() -> CompoundPath:
    """Generic symmetric diamond/bowtie proxy — not a reproduction of any
    specific "scales of justice" artwork.
    """
    outer = Circle(Point(0, 0), 25).to_path()
    bowtie = Polygon((Point(-14, 0), Point(0, -6), Point(14, 0), Point(0, 6))).to_path()
    return CompoundPath((outer, bowtie))


def school_seal() -> CompoundPath:
    outer = Circle(Point(0, 0), 25).to_path()
    return CompoundPath((outer, star(points=5, outer_radius=14, inner_radius=6).to_path()))


def government_seal() -> CompoundPath:
    """Multiple nested borders (three alternating-winding rings)."""
    outer = Circle(Point(0, 0), 25).to_path()
    ring1 = Polygon(tuple(reversed(_ring_points(0, 0, 22)))).to_path()
    ring2 = Circle(Point(0, 0), 19).to_path()
    ring3 = Polygon(tuple(reversed(_ring_points(0, 0, 16)))).to_path()
    ring4 = Circle(Point(0, 0), 13).to_path()
    return CompoundPath((outer, ring1, ring2, ring3, ring4))


def complex_circular_seal() -> CompoundPath:
    """Nested borders plus a ring of small tick marks simulating a text
    band around the perimeter.
    """
    outer = Circle(Point(0, 0), 25).to_path()
    inner_border = Polygon(tuple(reversed(_ring_points(0, 0, 21)))).to_path()
    ticks = []
    for i in range(36):
        angle = 2 * math.pi * i / 36
        cx, cy = 23 * math.cos(angle), 23 * math.sin(angle)
        ticks.append(
            Polygon(
                (Point(cx - 0.3, cy - 0.8), Point(cx + 0.3, cy - 0.8), Point(cx, cy + 0.8))
            ).to_path()
        )
    return CompoundPath((outer, inner_border, *ticks))


def star(points: int = 5, outer_radius: float = 14, inner_radius: float = 6) -> Polygon:
    coords = []
    for i in range(points * 2):
        r = outer_radius if i % 2 == 0 else inner_radius
        angle = math.pi / 2 + i * math.pi / points
        coords.append(Point(r * math.cos(angle), r * math.sin(angle)))
    return Polygon(tuple(coords))


def stars_fixture() -> CompoundPath:
    outer = Circle(Point(0, 0), 25).to_path()
    return CompoundPath((outer, star().to_path()))


def laurel_wreath() -> CompoundPath:
    """A generic wreath-like arrangement: small leaf-shaped polygons along
    two symmetric arcs — a structural stand-in, not a reproduction of any
    specific trademarked wreath artwork.
    """
    outer = Circle(Point(0, 0), 25).to_path()
    leaves = []
    for side in (-1, 1):
        for i in range(8):
            t = i / 7
            angle = math.pi * (0.15 + 0.6 * t)
            cx, cy = side * 20 * math.sin(angle), -20 * math.cos(angle) + 5
            leaves.append(
                Polygon(
                    (Point(cx - 1.5, cy), Point(cx, cy + 3), Point(cx + 1.5, cy), Point(cx, cy - 1))
                ).to_path()
            )
    return CompoundPath((outer, *leaves))


def _text_block(cx: float, cy: float, height: float, count: int, gap: float) -> list:
    blocks = []
    width = height * 0.6
    x = cx - (count * (width + gap)) / 2
    for _ in range(count):
        blocks.append(
            Polygon(
                (
                    Point(x, cy - height / 2),
                    Point(x + width, cy - height / 2),
                    Point(x + width, cy + height / 2),
                    Point(x, cy + height / 2),
                )
            ).to_path()
        )
        x += width + gap
    return blocks


def tiny_text_seal() -> CompoundPath:
    outer = Circle(Point(0, 0), 25).to_path()
    text = _text_block(0, -10, height=3.0, count=10, gap=0.5)
    return CompoundPath((outer, *text))


def micro_text_seal() -> CompoundPath:
    """Text near/at the minimum text height threshold — expected to
    surface min_text_height / node-density / tiny-area warnings.
    """
    outer = Circle(Point(0, 0), 25).to_path()
    text = _text_block(0, -10, height=1.0, count=14, gap=0.15)
    return CompoundPath((outer, *text))


def dense_logo() -> CompoundPath:
    """Many small close-together details — stresses spacing/density
    checks and island-merge search radius.
    """
    outer = Circle(Point(0, 0), 25).to_path()
    dots = []
    for gx in range(-3, 4):
        for gy in range(-3, 4):
            dots.append(Circle(Point(gx * 2.5, gy * 2.5), 0.6).to_path())
    return CompoundPath((outer, *dots))


def multiple_nested_borders() -> CompoundPath:
    outer = Circle(Point(0, 0), 25).to_path()
    borders = []
    radii = [22, 19, 16, 13, 10]
    for i, r in enumerate(radii):
        pts = _ring_points(0, 0, r)
        borders.append(Polygon(tuple(reversed(pts)) if i % 2 == 0 else pts).to_path())
    return CompoundPath((outer, *borders))


def signature_logo() -> CompoundPath:
    """A smooth, open wavy stroke (Catmull-Rom through control points) —
    representative of a handwritten-signature-style logo element.
    """
    from core.engines.geometry.simplify import smooth_points

    control_points = tuple(
        Point(x, 5 * math.sin(x / 3) + (2 if x % 6 < 3 else -2)) for x in range(-20, 21, 4)
    )
    path = smooth_points(control_points, closed=False)
    return CompoundPath((path,))


ALL_FIXTURES: dict[str, "callable"] = {
    "corporate_seal": corporate_seal,
    "doctor_seal": doctor_seal,
    "hospital_seal": hospital_seal,
    "architect_seal": architect_seal,
    "lawyer_seal": lawyer_seal,
    "school_seal": school_seal,
    "church_seal": church_seal,
    "government_seal": government_seal,
    "complex_circular_seal": complex_circular_seal,
    "tiny_text_seal": tiny_text_seal,
    "micro_text_seal": micro_text_seal,
    "dense_logo": dense_logo,
    "multiple_nested_borders": multiple_nested_borders,
    "stars_fixture": stars_fixture,
    "laurel_wreath": laurel_wreath,
    "signature_logo": signature_logo,
}
