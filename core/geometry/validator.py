"""Interface-level NeutralGeometry validation (TDD §5, §6 "Validation on
load" precedent applied to geometry payloads).

Scope, deliberately narrow: required fields present, correct types,
enum values valid, numeric fields actually numeric, subpaths/nodes
well-formed. This is *not* the Geometry Validation Engine's eleven
manufacturing defect checks (open curves, self-intersections, min
bridge, etc. — TDD §6.2/FR-6) — those require real geometry math and
arrive in their own sprint. This module only confirms the payload is
*shaped* like a NeutralGeometry the rest of Core could operate on.
"""
from __future__ import annotations

from typing import Any

from core.exceptions import GeometryFormatException
from core.geometry.models import FILL_TYPES, NODE_TYPES


def validate_geometry_dict(d: Any) -> list[str]:
    """Returns a list of human-readable issues (empty = valid). Never
    raises — callers decide whether an empty vs. non-empty list means
    "raise" (API layer) or "just tell me" (a future /validate-format
    diagnostic that wants a report, not an exception).
    """
    issues: list[str] = []

    if not isinstance(d, dict):
        return ["payload must be a JSON object"]

    _require_str(d, "units", issues)
    if d.get("units") not in (None, "mm"):
        issues.append("units must be 'mm' (TDD §5.2)")

    _validate_bounding_box(d.get("bounding_box"), issues)
    _validate_metadata(d.get("metadata"), issues)

    layers = d.get("layers")
    if layers is None:
        issues.append("layers is required")
    elif not isinstance(layers, (list, tuple)):
        issues.append("layers must be an array")
    else:
        for i, layer in enumerate(layers):
            _validate_layer(layer, i, issues)

    return issues


def validate_geometry_dict_or_raise(d: Any) -> None:
    issues = validate_geometry_dict(d)
    if issues:
        raise GeometryFormatException(
            "NeutralGeometry payload failed structural validation",
            context={"issues": issues},
        )


def _require_str(d: dict, key: str, issues: list[str]) -> None:
    if key not in d:
        issues.append(f"{key} is required")
    elif not isinstance(d[key], str) or not d[key]:
        issues.append(f"{key} must be a non-empty string")


def _require_number(d: dict, key: str, path: str, issues: list[str]) -> None:
    if key not in d:
        issues.append(f"{path}.{key} is required")
    elif not isinstance(d[key], (int, float)) or isinstance(d[key], bool):
        issues.append(f"{path}.{key} must be a number")


def _validate_bounding_box(bbox: Any, issues: list[str]) -> None:
    if bbox is None:
        issues.append("bounding_box is required")
        return
    if not isinstance(bbox, dict):
        issues.append("bounding_box must be an object")
        return
    for key in ("x", "y", "width", "height"):
        _require_number(bbox, key, "bounding_box", issues)


def _validate_metadata(meta: Any, issues: list[str]) -> None:
    if meta is None:
        issues.append("metadata is required")
        return
    if not isinstance(meta, dict):
        issues.append("metadata must be an object")
        return
    _require_str(meta, "source_adapter", issues)


def _validate_layer(layer: Any, index: int, issues: list[str]) -> None:
    path = f"layers[{index}]"
    if not isinstance(layer, dict):
        issues.append(f"{path} must be an object")
        return
    _require_str(layer, "layer_role", issues)
    objects = layer.get("objects", [])
    if not isinstance(objects, (list, tuple)):
        issues.append(f"{path}.objects must be an array")
        return
    for j, obj in enumerate(objects):
        _validate_object(obj, f"{path}.objects[{j}]", issues)


def _validate_object(obj: Any, path: str, issues: list[str]) -> None:
    if not isinstance(obj, dict):
        issues.append(f"{path} must be an object")
        return
    _require_str(obj, "object_id", issues)
    subpaths = obj.get("subpaths", [])
    if not isinstance(subpaths, (list, tuple)):
        issues.append(f"{path}.subpaths must be an array")
        return
    for k, subpath in enumerate(subpaths):
        _validate_subpath(subpath, f"{path}.subpaths[{k}]", issues)

    fill = obj.get("fill")
    if fill is not None:
        if not isinstance(fill, dict):
            issues.append(f"{path}.fill must be an object")
        elif fill.get("type") is not None and fill.get("type") not in FILL_TYPES:
            issues.append(f"{path}.fill.type must be one of {FILL_TYPES}")


def _validate_subpath(subpath: Any, path: str, issues: list[str]) -> None:
    if not isinstance(subpath, dict):
        issues.append(f"{path} must be an object")
        return
    if not isinstance(subpath.get("closed"), bool):
        issues.append(f"{path}.closed must be a boolean")
    nodes = subpath.get("nodes", [])
    if not isinstance(nodes, (list, tuple)):
        issues.append(f"{path}.nodes must be an array")
        return
    if len(nodes) == 0:
        issues.append(f"{path}.nodes must not be empty")
    for m, node in enumerate(nodes):
        _validate_node(node, f"{path}.nodes[{m}]", issues)


def _validate_node(node: Any, path: str, issues: list[str]) -> None:
    if not isinstance(node, dict):
        issues.append(f"{path} must be an object")
        return
    _require_number(node, "x", path, issues)
    _require_number(node, "y", path, issues)
    if node.get("node_type") not in NODE_TYPES:
        issues.append(f"{path}.node_type must be one of {NODE_TYPES}")
