from core.engines.geometry.io.dxf_io import DxfLayer, build_dxf
from core.engines.geometry.model import Circle, CompoundPath, Point
from core.engines.manufacturing.male_female import generate_male_female
from core.engines.manufacturing.rdworks_layers import (
    LAYER_COLOR_MAP,
    male_die_production_layers,
)
from core.engines.manufacturing.rules import RuleSet

RULE_SET = RuleSet.load_default()


def _structurally_valid_dxf(text: str) -> bool:
    lines = text.strip("\n").split("\n")
    if len(lines) % 2 != 0:
        return False
    for code in lines[0::2]:
        int(code)
    return lines.count("SECTION") == lines.count("ENDSEC") and lines[-1] == "EOF"


def test_build_dxf_is_structurally_valid():
    circle = Circle(Point(0, 0), 10).to_path()
    dxf = build_dxf([DxfLayer("TEST", 7, CompoundPath((circle,)))])
    assert _structurally_valid_dxf(dxf)
    assert "ARC" in dxf
    assert "TEST" in dxf


def test_male_die_production_layers_excludes_reference_geometry():
    circle = Circle(Point(0, 0), 20)
    mf = generate_male_female(circle, RULE_SET)
    layers = male_die_production_layers(mf)
    names = [layer.name for layer in layers]
    assert "MALE_CUT" in names
    assert "ORIGINAL" not in names
    assert "FEMALE_CUT" not in names
    dxf = build_dxf(layers, tolerance=RULE_SET.flatten_tolerance_mm)
    assert _structurally_valid_dxf(dxf)


def test_layer_color_map_has_an_entry_for_every_production_layer():
    for name in ("MALE_CUT", "FEMALE_CUT", "REGISTRATION", "ALIGNMENT"):
        assert name in LAYER_COLOR_MAP
