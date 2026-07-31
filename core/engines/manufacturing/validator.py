"""Manufacturing Validator. Distinct from the Geometry Engine's
`validation.py` (which only checks structural soundness — open curves,
NaN coordinates, etc.). This module answers manufacturing-specific
questions using a `RuleSet` (core.engines.manufacturing.rules) for every
threshold — generates structured `ManufacturingWarning` records, never
raises for a "the geometry is bad" finding (only for genuinely unusable
input, e.g. empty geometry).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from core.engines.geometry.model import Shape, as_compound
from core.engines.manufacturing.analysis_utils import (
    classify_subpaths,
    interior_angle_degrees,
    min_distance_between_rings,
    min_self_distance,
    path_node_density,
)
from core.engines.manufacturing.rules import RuleSet


class WarningType(Enum):
    THIN_LINE = "thin_line"
    TINY_HOLE = "tiny_hole"
    TINY_ISLAND = "tiny_island"
    FLOATING_GEOMETRY = "floating_geometry"
    WEAK_BRIDGE = "weak_bridge"
    SHARP_INTERNAL_CORNER = "sharp_internal_corner"
    SMALL_ENCLOSED_REGION = "small_enclosed_region"
    DISCONNECTED_GEOMETRY = "disconnected_geometry"
    MIN_SPACING_VIOLATION = "min_spacing_violation"
    NODE_DENSITY_VIOLATION = "node_density_violation"


@dataclass(frozen=True)
class ManufacturingWarning:
    warning_type: WarningType
    subpath_index: int
    detail: str
    measured_value: float
    threshold_value: float
    related_subpath_index: int | None = None


def _check_thin_lines(infos, rule_set: RuleSet) -> list[ManufacturingWarning]:
    """Proxy for "is any part of this shape narrower than min_line_width":
    the minimum distance between non-adjacent edges of the same subpath
    (the same proxy `_check_weak_bridges` uses for narrow necks, just
    thresholded against min_line_width_mm instead of
    min_bridge_width_mm). Deliberately *not* implemented via erosion
    (offsetting the ring inward by half the width): a naive per-edge
    offset can silently invert once it shrinks past a shape's own local
    width, producing a wrong (non-collapsed) result instead of
    signaling "this collapsed" — confirmed while testing this exact
    check. The edge-distance proxy has no such failure mode.
    """
    warnings = []
    for info in infos:
        if info.area <= 0 or len(info.ring) < 4:
            continue
        distance, i, j = min_self_distance(info.ring)
        if distance < rule_set.min_line_width_mm:
            warnings.append(
                ManufacturingWarning(
                    WarningType.THIN_LINE,
                    info.index,
                    f"Narrowest local width {distance:.4g}mm (edges {i}/{j}) "
                    f"below min_line_width_mm={rule_set.min_line_width_mm}",
                    distance,
                    rule_set.min_line_width_mm,
                )
            )
    return warnings


def _check_holes_and_islands(infos, rule_set: RuleSet) -> list[ManufacturingWarning]:
    warnings = []
    for info in infos:
        if info.area <= 0 or info.area >= rule_set.min_enclosed_area_mm2:
            continue
        if info.is_hole:
            warnings.append(
                ManufacturingWarning(
                    WarningType.TINY_HOLE,
                    info.index,
                    f"Hole area {info.area:.4g}mm2 below minimum",
                    info.area,
                    rule_set.min_enclosed_area_mm2,
                )
            )
        else:
            warnings.append(
                ManufacturingWarning(
                    WarningType.TINY_ISLAND,
                    info.index,
                    f"Island area {info.area:.4g}mm2 below minimum",
                    info.area,
                    rule_set.min_enclosed_area_mm2,
                )
            )
            warnings.append(
                ManufacturingWarning(
                    WarningType.SMALL_ENCLOSED_REGION,
                    info.index,
                    f"Enclosed region area {info.area:.4g}mm2 below minimum",
                    info.area,
                    rule_set.min_enclosed_area_mm2,
                )
            )
    return warnings


def _check_floating_and_disconnected(infos, rule_set: RuleSet) -> list[ManufacturingWarning]:
    """A subpath not nested as a hole in anything, and not the largest
    (presumed main body) subpath, is flagged as floating/disconnected.
    """
    warnings = []
    if not infos:
        return warnings
    main_index = max(infos, key=lambda i: i.area).index
    for info in infos:
        if info.is_hole or info.index == main_index or info.area <= 0:
            continue
        warnings.append(
            ManufacturingWarning(
                WarningType.FLOATING_GEOMETRY,
                info.index,
                "Subpath is a separate, non-hole region distinct from the main body",
                info.area,
                rule_set.min_enclosed_area_mm2,
            )
        )
        warnings.append(
            ManufacturingWarning(
                WarningType.DISCONNECTED_GEOMETRY,
                info.index,
                "Subpath is not connected to the main body",
                info.area,
                rule_set.min_enclosed_area_mm2,
                related_subpath_index=main_index,
            )
        )
    return warnings


def _check_weak_bridges(infos, rule_set: RuleSet) -> list[ManufacturingWarning]:
    warnings = []
    for info in infos:
        if len(info.ring) < 4:
            continue
        distance, i, j = min_self_distance(info.ring)
        if distance < rule_set.min_bridge_width_mm:
            warnings.append(
                ManufacturingWarning(
                    WarningType.WEAK_BRIDGE,
                    info.index,
                    f"Narrow neck ({distance:.4g}mm) between edges {i} and {j}",
                    distance,
                    rule_set.min_bridge_width_mm,
                )
            )
    return warnings


def _check_sharp_corners(infos, rule_set: RuleSet) -> list[ManufacturingWarning]:
    warnings = []
    for info in infos:
        n = len(info.ring)
        if n < 3:
            continue
        for k in range(n):
            angle = interior_angle_degrees(
                info.ring[(k - 1) % n], info.ring[k], info.ring[(k + 1) % n]
            )
            if angle < rule_set.sharp_corner_angle_threshold_degrees:
                warnings.append(
                    ManufacturingWarning(
                        WarningType.SHARP_INTERNAL_CORNER,
                        info.index,
                        f"Interior angle {angle:.1f} degrees at vertex {k}",
                        angle,
                        rule_set.sharp_corner_angle_threshold_degrees,
                    )
                )
    return warnings


def _check_min_spacing(infos, rule_set: RuleSet) -> list[ManufacturingWarning]:
    warnings = []
    for a in range(len(infos)):
        for b in range(a + 1, len(infos)):
            info_a, info_b = infos[a], infos[b]
            if len(info_a.ring) < 2 or len(info_b.ring) < 2:
                continue
            if info_a.is_hole or info_b.is_hole:
                continue
            distance, i, j = min_distance_between_rings(info_a.ring, info_b.ring)
            if distance < rule_set.min_spacing_mm:
                warnings.append(
                    ManufacturingWarning(
                        WarningType.MIN_SPACING_VIOLATION,
                        info_a.index,
                        f"Only {distance:.4g}mm from subpath {info_b.index}",
                        distance,
                        rule_set.min_spacing_mm,
                        related_subpath_index=info_b.index,
                    )
                )
    return warnings


def _check_node_density(infos, rule_set: RuleSet) -> list[ManufacturingWarning]:
    warnings = []
    for info in infos:
        density = path_node_density(info.path, rule_set.flatten_tolerance_mm)
        if density > rule_set.max_node_density_per_mm:
            warnings.append(
                ManufacturingWarning(
                    WarningType.NODE_DENSITY_VIOLATION,
                    info.index,
                    f"{density:.2f} nodes/mm exceeds maximum",
                    density,
                    rule_set.max_node_density_per_mm,
                )
            )
    return warnings


def validate_manufacturing(shape: Shape, rule_set: RuleSet) -> list[ManufacturingWarning]:
    compound = as_compound(shape)
    infos = classify_subpaths(compound, rule_set.flatten_tolerance_mm)

    warnings: list[ManufacturingWarning] = []
    warnings.extend(_check_thin_lines(infos, rule_set))
    warnings.extend(_check_holes_and_islands(infos, rule_set))
    warnings.extend(_check_floating_and_disconnected(infos, rule_set))
    warnings.extend(_check_weak_bridges(infos, rule_set))
    warnings.extend(_check_sharp_corners(infos, rule_set))
    warnings.extend(_check_min_spacing(infos, rule_set))
    warnings.extend(_check_node_density(infos, rule_set))
    return warnings
