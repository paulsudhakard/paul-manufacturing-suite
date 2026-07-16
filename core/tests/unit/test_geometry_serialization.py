from core.geometry import (
    BoundingBox,
    Fill,
    GeometryMetadata,
    GeometryObject,
    Layer,
    NeutralGeometry,
    Node,
    Subpath,
    assert_round_trip,
    geometry_from_dict,
    geometry_from_json,
    geometry_to_dict,
    geometry_to_json,
)
from core.geometry.roundtrip import RoundTripViolation


def make_geometry():
    return NeutralGeometry(
        units="mm",
        bounding_box=BoundingBox(0, 0, 20, 20),
        layers=(
            Layer(
                "original",
                (
                    GeometryObject(
                        "o1",
                        (Subpath(True, (Node(0, 0, "line"), Node(20, 0, "line"))),),
                        Fill("none", None),
                    ),
                ),
            ),
        ),
        metadata=GeometryMetadata("coreldraw", "test.cdr", "2026-01-01T00:00:00Z"),
    )


def test_dict_round_trip_is_lossless():
    geo = make_geometry()
    restored = geometry_from_dict(geometry_to_dict(geo))
    assert restored == geo


def test_json_round_trip_is_lossless():
    geo = make_geometry()
    restored = geometry_from_json(geometry_to_json(geo))
    assert restored == geo


def test_assert_round_trip_passes_for_identical_geometry():
    geo = make_geometry()
    assert_round_trip(geo, geo, epsilon=0.001)


def test_assert_round_trip_fails_when_node_moves_beyond_epsilon():
    geo = make_geometry()
    moved = geometry_from_dict(geometry_to_dict(geo))
    # Nudge one node coordinate beyond epsilon via dict surgery
    d = geometry_to_dict(geo)
    d["layers"][0]["objects"][0]["subpaths"][0]["nodes"][0]["x"] += 1.0
    moved = geometry_from_dict(d)
    try:
        assert_round_trip(geo, moved, epsilon=0.001)
        assert False, "expected RoundTripViolation"
    except RoundTripViolation:
        pass


def test_assert_round_trip_passes_within_epsilon():
    geo = make_geometry()
    d = geometry_to_dict(geo)
    d["layers"][0]["objects"][0]["subpaths"][0]["nodes"][0]["x"] += 0.0001
    nudged = geometry_from_dict(d)
    assert_round_trip(geo, nudged, epsilon=0.001)
