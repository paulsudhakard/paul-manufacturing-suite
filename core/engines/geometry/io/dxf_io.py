"""Minimal ASCII DXF (R12-compatible subset) writer. Supports LINE, ARC,
and CIRCLE entities only — sufficient for laser-cutting workflows
(RDWorks, LightBurn, etc. all read this subset natively). Bezier
segments are flattened to short LINE segments on export (DXF's base
entity set has no cubic-Bezier primitive); circular arcs export exactly
via the native ARC entity — no approximation needed there.

This is deliberately NOT a full DXF specification implementation — no
BLOCKS section, no support for other entity types.
"""

from __future__ import annotations

import math

from core.engines.geometry.flatten import DEFAULT_TOLERANCE_MM, flatten_bezier
from core.engines.geometry.model import (
    ArcSegment,
    BezierSegment,
    CompoundPath,
    LineSegment,
    Path,
    Point,
    Segment,
)


class DxfLayer:
    def __init__(self, name: str, color_index: int, compound: CompoundPath) -> None:
        self.name = name
        self.color_index = color_index
        self.compound = compound


def _dxf_group(code: int, value) -> str:
    return f"{code}\n{value}\n"


def _line_entity(layer: str, p1: Point, p2: Point) -> str:
    out = _dxf_group(0, "LINE")
    out += _dxf_group(8, layer)
    out += _dxf_group(10, f"{p1.x:.6f}")
    out += _dxf_group(20, f"{p1.y:.6f}")
    out += _dxf_group(11, f"{p2.x:.6f}")
    out += _dxf_group(21, f"{p2.y:.6f}")
    return out


def _arc_entity(layer: str, arc: ArcSegment) -> str:
    start_deg = math.degrees(arc.start_angle()) % 360
    end_deg = math.degrees(arc.end_angle()) % 360
    if arc.clockwise:
        start_deg, end_deg = end_deg, start_deg
    out = _dxf_group(0, "ARC")
    out += _dxf_group(8, layer)
    out += _dxf_group(10, f"{arc.center.x:.6f}")
    out += _dxf_group(20, f"{arc.center.y:.6f}")
    out += _dxf_group(40, f"{arc.radius:.6f}")
    out += _dxf_group(50, f"{start_deg:.6f}")
    out += _dxf_group(51, f"{end_deg:.6f}")
    return out


def _segment_to_entities(layer: str, segment: Segment, tolerance: float) -> str:
    if isinstance(segment, LineSegment):
        return _line_entity(layer, segment.start, segment.end)
    if isinstance(segment, ArcSegment):
        return _arc_entity(layer, segment)
    if isinstance(segment, BezierSegment):
        points = flatten_bezier(segment, tolerance) + (segment.end,)
        return "".join(
            _line_entity(layer, points[i], points[i + 1]) for i in range(len(points) - 1)
        )
    raise TypeError(f"Unknown segment type: {type(segment)}")


def _path_to_entities(layer: str, path: Path, tolerance: float) -> str:
    return "".join(_segment_to_entities(layer, s, tolerance) for s in path.segments)


def _compound_to_entities(layer: str, compound: CompoundPath, tolerance: float) -> str:
    return "".join(_path_to_entities(layer, p, tolerance) for p in compound.paths)


def build_dxf(layers: list[DxfLayer], tolerance: float = DEFAULT_TOLERANCE_MM) -> str:
    """A complete, minimal, valid DXF R12 document. TABLES/LAYER entries
    are included so layer names/colors are honored by readers that check
    the layer table rather than inferring from entities alone.
    """
    out = "0\nSECTION\n2\nTABLES\n"
    out += "0\nTABLE\n2\nLAYER\n"
    out += _dxf_group(70, len(layers))
    for layer in layers:
        out += _dxf_group(0, "LAYER")
        out += _dxf_group(2, layer.name)
        out += _dxf_group(70, 0)
        out += _dxf_group(62, layer.color_index)
        out += _dxf_group(6, "CONTINUOUS")
    out += "0\nENDTAB\n0\nENDSEC\n"

    out += "0\nSECTION\n2\nENTITIES\n"
    for layer in layers:
        out += _compound_to_entities(layer.name, layer.compound, tolerance)
    out += "0\nENDSEC\n0\nEOF\n"
    return out


def export_dxf_file(
    layers: list[DxfLayer], path: str, tolerance: float = DEFAULT_TOLERANCE_MM
) -> None:
    content = build_dxf(layers, tolerance)
    with open(path, "w", newline="\r\n") as f:
        f.write(content)
