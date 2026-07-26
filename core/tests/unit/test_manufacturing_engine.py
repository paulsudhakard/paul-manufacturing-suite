from core.engines.geometry.model import Circle, CompoundPath, Point, Polygon
from core.engines.manufacturing.male_female import (
    female_offset_distance,
    generate_male_female,
    male_offset_distance,
)
from core.engines.manufacturing.repair import (
    merge_tiny_islands,
    remove_tiny_holes,
    repair_manufacturing,
    round_sharp_corners,
    widen_weak_bridges,
)
from core.engines.manufacturing.rules import RuleSet
from core.engines.manufacturing.validator import WarningType, validate_manufacturing

RULE_SET = RuleSet.load_default()


def test_ruleset_loads_default_and_rejects_bad_keys(tmp_path):
    rs = RuleSet.load_default()
    assert rs.min_bridge_width_mm == 0.8

    bad_path = tmp_path / "bad.yaml"
    bad_path.write_text("min_line_width_mm: 0.5\n")  # missing required keys
    try:
        RuleSet.load(bad_path)
        assert False, "expected ValueError for missing keys"
    except ValueError:
        pass


def test_clean_circle_has_no_warnings():
    shape = Circle(Point(0, 0), 25).to_path()
    assert validate_manufacturing(CompoundPath((shape,)), RULE_SET) == []


def test_true_hole_vs_island_classification():
    outer = Polygon((Point(0, 0), Point(50, 0), Point(50, 50), Point(0, 50))).to_path()
    true_hole = Polygon((Point(24, 24), Point(24, 25), Point(25, 25), Point(25, 24))).to_path()
    w = [x.warning_type for x in validate_manufacturing(CompoundPath((outer, true_hole)), RULE_SET)]
    assert WarningType.TINY_HOLE in w and WarningType.TINY_ISLAND not in w

    true_island = Polygon(
        (Point(10, 10), Point(10.5, 10), Point(10.5, 10.5), Point(10, 10.5))
    ).to_path()
    w2 = [
        x.warning_type for x in validate_manufacturing(CompoundPath((outer, true_island)), RULE_SET)
    ]
    assert WarningType.TINY_ISLAND in w2 and WarningType.TINY_HOLE not in w2


def test_thin_line_detected():
    thin = Polygon((Point(0, 0), Point(20, 0), Point(20, 0.2), Point(0, 0.2))).to_path()
    w = [x.warning_type for x in validate_manufacturing(CompoundPath((thin,)), RULE_SET)]
    assert WarningType.THIN_LINE in w


def test_weak_bridge_detected_but_not_on_smooth_circle():
    circle = Circle(Point(0, 0), 25).to_path()
    w = [x.warning_type for x in validate_manufacturing(CompoundPath((circle,)), RULE_SET)]
    assert WarningType.WEAK_BRIDGE not in w  # regression: tessellation false-positive fix

    dumbbell = Polygon(
        (
            Point(-10, -5), Point(-10, 5), Point(-2, 0.15), Point(2, 0.15),
            Point(10, 5), Point(10, -5), Point(2, -0.15), Point(-2, -0.15),
        )
    ).to_path()
    w2 = [x.warning_type for x in validate_manufacturing(CompoundPath((dumbbell,)), RULE_SET)]
    assert WarningType.WEAK_BRIDGE in w2


def test_remove_tiny_holes():
    outer = Polygon((Point(0, 0), Point(50, 0), Point(50, 50), Point(0, 50))).to_path()
    hole = Polygon((Point(24, 24), Point(24, 25), Point(25, 25), Point(25, 24))).to_path()
    fixed, actions = remove_tiny_holes(CompoundPath((outer, hole)), RULE_SET)
    assert len(fixed.paths) == 1 and actions


def test_merge_tiny_islands():
    outer = Polygon((Point(0, 0), Point(50, 0), Point(50, 50), Point(0, 50))).to_path()
    island = Polygon(
        (Point(10, 10), Point(10.5, 10), Point(10.5, 10.5), Point(10, 10.5))
    ).to_path()
    fixed, actions = merge_tiny_islands(CompoundPath((outer, island)), RULE_SET)
    assert len(fixed.paths) == 1 and actions


def test_round_sharp_corners_removes_the_warning():
    from core.engines.geometry.flatten import flatten_path
    from core.engines.manufacturing.analysis_utils import interior_angle_degrees

    notch = Polygon(
        (
            Point(0, 0), Point(20, 0), Point(20, 20), Point(11, 20),
            Point(10, 15), Point(9, 20), Point(0, 20),
        )
    ).to_path()
    fixed, actions = round_sharp_corners(CompoundPath((notch,)), RULE_SET)
    assert actions
    flat = flatten_path(fixed.paths[0], RULE_SET.flatten_tolerance_mm)
    ring = flat[:-1] if flat[0] == flat[-1] else flat
    n = len(ring)
    angles = [
        interior_angle_degrees(ring[(k - 1) % n], ring[k], ring[(k + 1) % n]) for k in range(n)
    ]
    assert min(angles) >= RULE_SET.sharp_corner_angle_threshold_degrees


def test_widen_weak_bridges_reaches_target_width():
    from core.engines.manufacturing.analysis_utils import classify_subpaths, min_self_distance

    narrow = Polygon((Point(0, 0), Point(10, 0), Point(10, 0.3), Point(0, 0.3))).to_path()
    fixed, actions = widen_weak_bridges(CompoundPath((narrow,)), RULE_SET)
    assert actions
    infos = classify_subpaths(fixed, RULE_SET.flatten_tolerance_mm)
    d, _, _ = min_self_distance(infos[0].ring)
    assert d >= RULE_SET.min_bridge_width_mm - 1e-6


def test_repair_manufacturing_is_deterministic_and_reports_similarity():
    outer = Polygon((Point(0, 0), Point(50, 0), Point(50, 50), Point(0, 50))).to_path()
    island = Polygon(
        (Point(10, 10), Point(10.5, 10), Point(10.5, 10.5), Point(10, 10.5))
    ).to_path()
    compound = CompoundPath((outer, island))
    result_a = repair_manufacturing(compound, RULE_SET)
    result_b = repair_manufacturing(compound, RULE_SET)
    assert result_a.compound == result_b.compound
    assert result_a.actions == result_b.actions
    assert 0.0 <= result_a.similarity <= 1.0


def test_male_female_offsets_move_in_opposite_directions():
    assert male_offset_distance(RULE_SET) != female_offset_distance(RULE_SET)
    assert female_offset_distance(RULE_SET) < 0  # female always shrinks inward


def test_generate_male_female_produces_valid_geometry():
    from core.engines.geometry.measure import area

    circle = Circle(Point(0, 0), 20)
    result = generate_male_female(circle, RULE_SET)
    assert area(result.male) > 0
    assert area(result.female) > 0
    assert len(result.registration) == 2
    assert len(result.alignment) == 1
