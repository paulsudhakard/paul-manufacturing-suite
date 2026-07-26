from core.validation_suite import (
    render_failure_report,
    render_summary_table,
    validate_single_artwork,
)

VALID_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40mm" height="40mm" viewBox="0 0 40 40">
  <circle cx="20" cy="20" r="18"/>
</svg>"""

BROKEN_XML_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40mm" height="40mm" viewBox="0 0 40 40">
  <circle cx="20" cy="20" r="18"
"""

EMPTY_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="10mm" height="10mm" viewBox="0 0 10 10"></svg>"""


def test_valid_artwork_passes_every_stage():
    result = validate_single_artwork(VALID_SVG, "clean.svg")
    assert result.overall_pass
    assert all(status == "PASS" for status in result.stage_status.values())
    assert result.result is not None
    assert result.result.dxf_text


def test_broken_xml_fails_at_import_stage_only():
    result = validate_single_artwork(BROKEN_XML_SVG, "broken.svg")
    assert not result.overall_pass
    assert result.failure_stage == "svg_import"
    assert result.stage_status["Import"] == "FAIL"
    # everything downstream of Import never ran
    for column in ("Validation", "Repair", "Male", "Female", "Preview", "DXF", "Report"):
        assert result.stage_status[column] == "NOT REACHED"
    assert result.failure_exception_type == "GeometryFormatException"
    assert result.result is None


def test_empty_svg_also_fails_at_import_stage():
    result = validate_single_artwork(EMPTY_SVG, "empty.svg")
    assert not result.overall_pass
    assert result.failure_stage == "svg_import"


def test_summary_table_has_exact_requested_column_order():
    result = validate_single_artwork(VALID_SVG, "clean.svg")
    table = render_summary_table([result])
    header = table.splitlines()[0]
    assert header == (
        "| Artwork | Import | Validation | Repair | Male | Female | Preview | DXF | Report | Pass/Fail |"
    )


def test_summary_table_reports_pass_and_fail_rows():
    passing = validate_single_artwork(VALID_SVG, "clean.svg")
    failing = validate_single_artwork(BROKEN_XML_SVG, "broken.svg")
    table = render_summary_table([passing, failing])
    assert "clean.svg" in table and "PASS" in table
    assert "broken.svg" in table and "FAIL" in table


def test_failure_report_identifies_responsible_module():
    result = validate_single_artwork(BROKEN_XML_SVG, "broken.svg")
    report = render_failure_report(result)
    assert "core.engines.geometry.io.svg_io" in report
    assert "GeometryFormatException" in report
    assert "broken.svg" in report


def test_failure_report_on_a_passing_result_says_no_failure():
    result = validate_single_artwork(VALID_SVG, "clean.svg")
    report = render_failure_report(result)
    assert "no failure" in report.lower()


def test_warnings_do_not_count_as_stage_failure():
    """A stage that finds manufacturing warnings still PASSES (it ran
    successfully and produced its output) -- pass/fail is about
    execution, not about whether the artwork is already
    manufacturing-clean.
    """
    seal_with_tiny_island = """<svg xmlns="http://www.w3.org/2000/svg" width="50mm" height="50mm" viewBox="0 0 50 50">
  <circle cx="25" cy="25" r="22"/>
  <circle cx="10" cy="10" r="0.3"/>
</svg>"""
    result = validate_single_artwork(seal_with_tiny_island, "tiny_island.svg")
    assert result.overall_pass
    assert result.stage_status["Validation"] == "PASS"
    assert len(result.result.manufacturing_warnings_before) > 0  # warnings exist...
    assert result.overall_pass  # ...but stage still passed
