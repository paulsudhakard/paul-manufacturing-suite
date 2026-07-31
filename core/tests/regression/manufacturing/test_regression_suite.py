"""Manufacturing regression suite. Every fixture in fixtures.py runs
through the full pipeline; failures here are exactly the "production
artwork exposes a weakness" signal the engineering rule requires acting
on (fix the generic algorithm, then this suite gains a permanent
regression fixture for it — real customer artwork, once supplied,
joins ALL_FIXTURES the same way).
"""

import math

import pytest

from core.engines.geometry.model import CompoundPath
from core.engines.geometry.validation import IssueType
from core.engines.manufacturing.pipeline import run_pipeline
from core.engines.manufacturing.rules import RuleSet
from core.tests.regression.manufacturing.fixtures import ALL_FIXTURES

RULE_SET = RuleSet.load_default()


def _assert_no_corruption(compound: CompoundPath):
    for path in compound.paths:
        for segment in path.segments:
            for attr in ("start", "end"):
                p = getattr(segment, attr)
                assert math.isfinite(p.x) and math.isfinite(p.y), f"non-finite coordinate: {p}"


@pytest.mark.parametrize("name", list(ALL_FIXTURES), ids=list(ALL_FIXTURES))
def test_pipeline_runs_without_corruption(name):
    shape = ALL_FIXTURES[name]()
    result = run_pipeline(shape, RULE_SET)

    _assert_no_corruption(result.repair.compound)
    _assert_no_corruption(result.male_female.male)
    _assert_no_corruption(result.male_female.female)

    invalid_coord_issues = [
        i for i in result.structural_issues_after if i.issue_type == IssueType.INVALID_COORDINATES
    ]
    assert invalid_coord_issues == [], f"{name}: corrupted coordinates after repair"

    assert result.dxf_text.strip().startswith("0\nSECTION")
    assert result.dxf_text.strip().endswith("EOF")
    lines = result.dxf_text.strip("\n").split("\n")
    assert len(lines) % 2 == 0, f"{name}: DXF group code/value lines don't pair up"


@pytest.mark.parametrize("name", list(ALL_FIXTURES), ids=list(ALL_FIXTURES))
def test_repair_is_deterministic(name):
    shape = ALL_FIXTURES[name]()
    result_a = run_pipeline(shape, RULE_SET)
    result_b = run_pipeline(shape, RULE_SET)
    assert result_a.repair.compound == result_b.repair.compound
    assert result_a.repair.actions == result_b.repair.actions
    assert result_a.repair.similarity == result_b.repair.similarity


@pytest.mark.parametrize("name", list(ALL_FIXTURES), ids=list(ALL_FIXTURES))
def test_male_female_generation_is_deterministic(name):
    shape = ALL_FIXTURES[name]()
    result_a = run_pipeline(shape, RULE_SET)
    result_b = run_pipeline(shape, RULE_SET)
    assert result_a.male_female.male == result_b.male_female.male
    assert result_a.male_female.female == result_b.male_female.female
    assert result_a.male_female.registration == result_b.male_female.registration
    assert result_a.male_female.alignment == result_b.male_female.alignment


@pytest.mark.parametrize("name", list(ALL_FIXTURES), ids=list(ALL_FIXTURES))
def test_warnings_are_always_threshold_driven(name):
    """Every warning must trace back to a configured threshold — never a
    fixture-specific carve-out (Engineering Rule: never patch a specific
    logo, always improve the generic algorithm).
    """
    shape = ALL_FIXTURES[name]()
    result = run_pipeline(shape, RULE_SET)
    for w in result.manufacturing_warnings_after:
        assert w.threshold_value > 0
