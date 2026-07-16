"""Serialization: NeutralGeometry <-> plain dict <-> JSON.

Deserialization (`from_dict`) does *not* perform semantic validation —
that's `core.geometry.validator`'s job, deliberately kept separate so
callers can choose "parse leniently, then validate with full error
detail" rather than getting a raw KeyError/TypeError from a strict
constructor.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from core.geometry.models import (
    BoundingBox,
    Fill,
    GeometryMetadata,
    GeometryObject,
    Layer,
    NeutralGeometry,
    Node,
    Point,
    Stroke,
    Subpath,
)


def geometry_to_dict(geometry: NeutralGeometry) -> dict[str, Any]:
    """dataclasses.asdict handles the full nested structure; Point/Node
    None fields serialize as JSON null naturally.
    """
    return asdict(geometry)


def geometry_to_json(geometry: NeutralGeometry) -> str:
    return json.dumps(geometry_to_dict(geometry))


def _point_from_dict(d: dict | None) -> Point | None:
    return None if d is None else Point(x=d["x"], y=d["y"])


def _node_from_dict(d: dict) -> Node:
    return Node(
        x=d["x"],
        y=d["y"],
        node_type=d["node_type"],
        control_in=_point_from_dict(d.get("control_in")),
        control_out=_point_from_dict(d.get("control_out")),
    )


def _subpath_from_dict(d: dict) -> Subpath:
    return Subpath(
        closed=d["closed"],
        nodes=tuple(_node_from_dict(n) for n in d.get("nodes", [])),
    )


def _object_from_dict(d: dict) -> GeometryObject:
    fill_d = d.get("fill") or {}
    stroke_d = d.get("stroke") or {}
    return GeometryObject(
        object_id=d["object_id"],
        subpaths=tuple(_subpath_from_dict(s) for s in d.get("subpaths", [])),
        fill=Fill(type=fill_d.get("type", "none"), color=fill_d.get("color")),
        stroke=Stroke(width=stroke_d.get("width")),
    )


def _layer_from_dict(d: dict) -> Layer:
    return Layer(
        layer_role=d["layer_role"],
        objects=tuple(_object_from_dict(o) for o in d.get("objects", [])),
    )


def geometry_from_dict(d: dict[str, Any]) -> NeutralGeometry:
    """Raises KeyError/TypeError on structurally malformed input — callers
    on the untrusted-input path (the API layer) should run this through
    `core.geometry.validator.validate_geometry_dict` first, which turns
    those into a structured GeometryFormatException instead.
    """
    bbox_d = d["bounding_box"]
    meta_d = d["metadata"]
    return NeutralGeometry(
        units=d["units"],
        bounding_box=BoundingBox(**bbox_d),
        layers=tuple(_layer_from_dict(layer) for layer in d.get("layers", [])),
        metadata=GeometryMetadata(
            source_adapter=meta_d["source_adapter"],
            source_file_hint=meta_d.get("source_file_hint"),
            imported_at=meta_d.get("imported_at"),
        ),
        format_version=d.get("format_version", "1.0"),
    )


def geometry_from_json(raw: str) -> NeutralGeometry:
    return geometry_from_dict(json.loads(raw))
