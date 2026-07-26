from core.validation_suite import render_summary_table, validate_artwork_directory

VALID_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="30mm" height="30mm" viewBox="0 0 30 30">
  <circle cx="15" cy="15" r="13"/>
</svg>"""

BROKEN_SVG = "<svg><path d="


def test_validate_artwork_directory_processes_every_svg_file(tmp_path):
    (tmp_path / "good.svg").write_text(VALID_SVG)
    (tmp_path / "bad.svg").write_text(BROKEN_SVG)
    (tmp_path / "not_svg.txt").write_text("ignore me")

    results = validate_artwork_directory(tmp_path)

    assert len(results) == 2  # only .svg files
    names = {r.filename for r in results}
    assert names == {"good.svg", "bad.svg"}

    good = next(r for r in results if r.filename == "good.svg")
    bad = next(r for r in results if r.filename == "bad.svg")
    assert good.overall_pass
    assert not bad.overall_pass


def test_validate_artwork_directory_isolates_failures(tmp_path):
    """One broken file must not prevent the others from being processed."""
    (tmp_path / "a_good.svg").write_text(VALID_SVG)
    (tmp_path / "b_broken.svg").write_text(BROKEN_SVG)
    (tmp_path / "c_good.svg").write_text(VALID_SVG)

    results = validate_artwork_directory(tmp_path)
    assert len(results) == 3
    passed = [r for r in results if r.overall_pass]
    failed = [r for r in results if not r.overall_pass]
    assert len(passed) == 2
    assert len(failed) == 1
    assert failed[0].filename == "b_broken.svg"


def test_end_to_end_summary_table_for_a_directory(tmp_path):
    (tmp_path / "seal_1.svg").write_text(VALID_SVG)
    results = validate_artwork_directory(tmp_path)
    table = render_summary_table(results)
    assert "seal_1.svg" in table
    assert "PASS" in table
    # every requested column present
    for column in ("Import", "Validation", "Repair", "Male", "Female", "Preview", "DXF", "Report"):
        assert column in table


def test_empty_directory_produces_empty_results(tmp_path):
    results = validate_artwork_directory(tmp_path)
    assert results == []
