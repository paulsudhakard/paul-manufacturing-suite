"""Neutral Geometry Format data model (TDD §5.2).

Plain dataclasses, not Pydantic — consistent with the rest of Core
(config/logging already use this style) and zero new runtime deps.
`format_version` is included per TDD §25 ("added to §5.2's top-level
object... required").
"""

from __future__ import annotations

from dataclasses import dataclass, field

FORMAT_VERSION = "1.0"

NODE_TYPES = ("line", "curve")
FILL_TYPES = ("none", "solid")


@dataclass(frozen=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Node:
    x: float
    y: float
    node_type: str  # "line" | "curve"
    control_in: Point | None = None
    control_out: Point | None = None


@dataclass(frozen=True)
class Subpath:
    closed: bool
    nodes: tuple[Node, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Fill:
    type: str = "none"  # "none" | "solid"
    color: str | None = None


@dataclass(frozen=True)
class Stroke:
    width: float | None = None


@dataclass(frozen=True)
class GeometryObject:
    object_id: str
    subpaths: tuple[Subpath, ...] = field(default_factory=tuple)
    fill: Fill = field(default_factory=Fill)
    stroke: Stroke = field(default_factory=Stroke)


@dataclass(frozen=True)
class Layer:
    layer_role: str  # e.g. "original" | "repair" | "male" | "female" | ...
    objects: tuple[GeometryObject, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class BoundingBox:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class GeometryMetadata:
    source_adapter: str
    source_file_hint: str | None = None
    imported_at: str | None = None  # ISO8601


@dataclass(frozen=True)
class NeutralGeometry:
    units: str
    bounding_box: BoundingBox
    layers: tuple[Layer, ...]
    metadata: GeometryMetadata
    format_version: str = FORMAT_VERSION
