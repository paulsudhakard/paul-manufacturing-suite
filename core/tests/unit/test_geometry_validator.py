from core.exceptions import GeometryFormatException
from core.geometry.validator import validate_geometry_dict, validate_geometry_dict_or_raise

VALID = {
    "units": "mm",
    "bounding_box": {"x": 0, "y": 0, "width": 10, "height": 10},
    "layers": [
        {
            "layer_role": "original",
            "objects": [
                {
                    "object_id": "o1",
                    "subpaths": [
                        {
                            "closed": True,
                            "nodes": [
                                {"x": 0, "y": 0, "node_type": "line"},
                                {"x": 10, "y": 0, "node_type": "line"},
                            ],
                        }
                    ],
                }
            ],
        }
    ],
    "metadata": {"source_adapter": "coreldraw"},
}


def test_valid_geometry_has_no_issues():
    assert validate_geometry_dict(VALID) == []


def test_not_a_dict():
    assert validate_geometry_dict([1, 2, 3]) == ["payload must be a JSON object"]


def test_missing_units():
    d = {k: v for k, v in VALID.items() if k != "units"}
    assert "units is required" in validate_geometry_dict(d)


def test_wrong_units_value():
    d = {**VALID, "units": "inches"}
    assert any("units must be 'mm'" in i for i in validate_geometry_dict(d))


def test_missing_bounding_box():
    d = {k: v for k, v in VALID.items() if k != "bounding_box"}
    assert "bounding_box is required" in validate_geometry_dict(d)


def test_bounding_box_bad_type():
    d = {**VALID, "bounding_box": {"x": "not-a-number", "y": 0, "width": 1, "height": 1}}
    assert any("bounding_box.x must be a number" in i for i in validate_geometry_dict(d))


def test_invalid_node_type():
    bad_node_geom = {
        **VALID,
        "layers": [
            {
                "layer_role": "original",
                "objects": [
                    {
                        "object_id": "o1",
                        "subpaths": [
                            {"closed": True, "nodes": [{"x": 0, "y": 0, "node_type": "spline"}]}
                        ],
                    }
                ],
            }
        ],
    }
    issues = validate_geometry_dict(bad_node_geom)
    assert any("node_type must be one of" in i for i in issues)


def test_empty_nodes_list_is_invalid():
    empty_nodes = {
        **VALID,
        "layers": [
            {
                "layer_role": "original",
                "objects": [{"object_id": "o1", "subpaths": [{"closed": True, "nodes": []}]}],
            }
        ],
    }
    issues = validate_geometry_dict(empty_nodes)
    assert any("nodes must not be empty" in i for i in issues)


def test_or_raise_raises_geometry_format_exception():
    try:
        validate_geometry_dict_or_raise({"units": "mm"})
        assert False, "expected GeometryFormatException"
    except GeometryFormatException as exc:
        assert exc.category == "validation"
        assert "issues" in exc.context


def test_or_raise_passes_on_valid_input():
    validate_geometry_dict_or_raise(VALID)  # must not raise
