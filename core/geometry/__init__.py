from core.geometry.interfaces import GeometryAdapter
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
from core.geometry.roundtrip import DEFAULT_EPSILON_MM, RoundTripViolation, assert_round_trip
from core.geometry.serialization import (
    geometry_from_dict,
    geometry_from_json,
    geometry_to_dict,
    geometry_to_json,
)
from core.geometry.validator import validate_geometry_dict, validate_geometry_dict_or_raise

__all__ = [
    "NeutralGeometry",
    "BoundingBox",
    "Layer",
    "GeometryObject",
    "Subpath",
    "Node",
    "Point",
    "Fill",
    "Stroke",
    "GeometryMetadata",
    "GeometryAdapter",
    "geometry_to_dict",
    "geometry_to_json",
    "geometry_from_dict",
    "geometry_from_json",
    "validate_geometry_dict",
    "validate_geometry_dict_or_raise",
    "assert_round_trip",
    "RoundTripViolation",
    "DEFAULT_EPSILON_MM",
]
