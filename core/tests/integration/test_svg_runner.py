"""Integration tests for tools/run_svg_pipeline.py.

Runs the CLI's `main()` in-process (same convention as
core/tests/integration/test_core_skeleton_startup.py) rather than via
subprocess, so failures show a normal Python traceback instead of an
opaque non-zero exit code.

Speed: the real orchestrator (all 10 pipeline stages) runs exactly
once for the "successful run" scenario, via the module-scoped
`successful_run` fixture below; every read-only assertion about that
run's output is a separate, single-responsibility test that reuses the
same fixture rather than re-running the pipeline. Error-path tests
(missing file, invalid SVG, invalid output directory) each fail before
or immediately at the SVG-parsing stage, so they're inherently cheap
and don't need sharing.

No mocking is used anywhere in this file: the orchestrator and every
engine it calls run for real. Nothing here depends on external
software, CorelDRAW, RDWorks, or network access -- every fixture is a
small inline SVG string, and every path is a pytest tmp_path.
"""

import contextlib
import io
import json
import os
from dataclasses import dataclass

import pytest

from tools.run_svg_pipeline import main

VALID_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="40mm" height="40mm"
     viewBox="0 0 40 40">
  <circle cx="20" cy="20" r="18"/>
</svg>"""

BROKEN_SVG = "<svg><path d="

EXPECTED_PROGRESS_LINES = [
    "[1/10] SVG Import",
    "[2/10] Geometry Validation",
    "[3/10] Geometry Repair",
    "[4/10] Manufacturing Validation",
    "[5/10] Manufacturing Repair",
    "[6/10] Male Generator",
    "[7/10] Female Generator",
    "[8/10] Preview Generation",
    "[9/10] DXF Export",
    "[10/10] Validation Report",
]


def _run_cli(argv: list[str]) -> tuple[int, str]:
    """Helper: invoke main() with stdout captured, return
    (exit_code, stdout_text). Captures via redirect_stdout (not
    pytest's capsys) so this helper can be called from a module-scoped
    fixture, where capsys isn't available.
    """
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        exit_code = main(argv)
    return exit_code, buffer.getvalue()


@dataclass(frozen=True)
class SuccessfulRun:
    exit_code: int
    stdout: str
    output_dir: object  # pathlib.Path


@pytest.fixture(scope="module")
def successful_run(tmp_path_factory) -> SuccessfulRun:
    """Runs the full pipeline against VALID_SVG exactly once, shared by
    every read-only assertion test below (requirement: keep total
    suite execution fast; requirement: reuse helpers where appropriate).
    """
    base = tmp_path_factory.mktemp("svg_runner_success")
    input_path = base / "logo.svg"
    input_path.write_text(VALID_SVG)
    output_dir = base / "output"

    exit_code, stdout = _run_cli(["--input", str(input_path), "--output", str(output_dir)])
    return SuccessfulRun(exit_code=exit_code, stdout=stdout, output_dir=output_dir)


# --- Successful run: one focused assertion per test -------------------------


def test_successful_run_exits_zero(successful_run):
    assert successful_run.exit_code == 0


def test_successful_run_creates_pipeline_dxf(successful_run):
    assert (successful_run.output_dir / "pipeline.dxf").exists()


def test_pipeline_dxf_has_valid_dxf_structure(successful_run):
    text = (successful_run.output_dir / "pipeline.dxf").read_text().strip()
    assert text.startswith("0\nSECTION")
    assert text.endswith("EOF")


def test_successful_run_creates_validation_report_json(successful_run):
    assert (successful_run.output_dir / "validation_report.json").exists()


def test_validation_report_is_valid_json(successful_run):
    text = (successful_run.output_dir / "validation_report.json").read_text()
    json.loads(text)  # raises if not valid JSON


def test_validation_report_contains_expected_keys(successful_run):
    report = json.loads((successful_run.output_dir / "validation_report.json").read_text())
    assert "geometry_issues_before" in report
    assert "geometry_repair_actions" in report
    assert "manufacturing_warnings_before" in report
    assert "manufacturing_warnings_after" in report
    assert "passed" in report


def test_successful_run_prints_completion_message(successful_run):
    assert "Pipeline completed successfully." in successful_run.stdout


def test_successful_run_prints_pipeline_passed_summary_field(successful_run):
    assert "Pipeline Passed:" in successful_run.stdout


def test_progress_callback_prints_all_ten_stages_in_order(successful_run):
    positions = [successful_run.stdout.index(line) for line in EXPECTED_PROGRESS_LINES]
    assert positions == sorted(positions)


def test_preview_serialization_message_when_unsupported(successful_run):
    """ManufacturingPreview has no to_dict/to_json/serialize method
    today, so the runner must print the documented fallback message
    rather than inventing serialization.
    """
    assert "Preview serialization is not implemented." in successful_run.stdout
    assert not (successful_run.output_dir / "preview.json").exists()


# --- Error paths: each is its own fast, independent invocation --------------


def test_missing_input_file_returns_nonzero(tmp_path):
    missing = tmp_path / "does_not_exist.svg"
    exit_code, _ = _run_cli(["--input", str(missing), "--output", str(tmp_path / "output")])
    assert exit_code != 0


def test_missing_input_file_error_is_user_friendly(tmp_path, capsys):
    missing = tmp_path / "does_not_exist.svg"
    main(["--input", str(missing), "--output", str(tmp_path / "output")])
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "not found" in captured.err.lower()


def test_non_svg_extension_is_rejected(tmp_path, capsys):
    text_file = tmp_path / "not_an_svg.txt"
    text_file.write_text("hello")
    exit_code = main(["--input", str(text_file), "--output", str(tmp_path / "output")])
    assert exit_code != 0
    captured = capsys.readouterr()
    assert "svg" in captured.err.lower()


def test_invalid_svg_content_returns_nonzero(tmp_path):
    broken = tmp_path / "broken.svg"
    broken.write_text(BROKEN_SVG)
    exit_code, _ = _run_cli(["--input", str(broken), "--output", str(tmp_path / "output")])
    assert exit_code != 0


def test_invalid_svg_content_is_user_friendly_without_debug(tmp_path, capsys):
    broken = tmp_path / "broken.svg"
    broken.write_text(BROKEN_SVG)
    main(["--input", str(broken), "--output", str(tmp_path / "output")])
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert captured.err.startswith("Error:")


def test_invalid_svg_content_shows_traceback_in_debug_mode(tmp_path, capsys):
    broken = tmp_path / "broken.svg"
    broken.write_text(BROKEN_SVG)
    exit_code = main(["--input", str(broken), "--output", str(tmp_path / "output"), "--debug"])
    assert exit_code != 0
    captured = capsys.readouterr()
    assert "Traceback" in captured.err


def test_invalid_output_directory_is_rejected(tmp_path, capsys):
    """--output points at a path where a plain file already exists --
    a directory can never be created there. Deterministic and portable
    (no chmod/permission tricks, which behave inconsistently across
    operating systems).
    """
    input_path = tmp_path / "logo.svg"
    input_path.write_text(VALID_SVG)
    blocked_output = tmp_path / "blocker"
    blocked_output.write_text("this is a file, not a directory")

    exit_code = main(["--input", str(input_path), "--output", str(blocked_output)])

    assert exit_code != 0
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "not a directory" in captured.err.lower()


def test_output_directory_is_created_automatically(tmp_path):
    input_path = tmp_path / "logo.svg"
    input_path.write_text(VALID_SVG)
    output_dir = tmp_path / "nested" / "does_not_exist_yet"
    assert not output_dir.exists()

    exit_code = main(["--input", str(input_path), "--output", str(output_dir)])

    assert exit_code == 0
    assert output_dir.exists()
    assert (output_dir / "pipeline.dxf").exists()


def test_help_flag_exits_zero_and_shows_usage(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "--input" in captured.out
    assert "--output" in captured.out
    assert "--debug" in captured.out


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root bypasses file permissions, so this check cannot be exercised meaningfully",
)
def test_permission_denied_reading_input_is_user_friendly(tmp_path, capsys):
    """Deterministic on a non-root run: chmod 000 makes the file
    genuinely unreadable regardless of file *contents*, so this needs
    no SVG-specific setup beyond an existing file.
    """
    input_path = tmp_path / "unreadable.svg"
    input_path.write_text(VALID_SVG)
    input_path.chmod(0o000)
    try:
        exit_code = main(["--input", str(input_path), "--output", str(tmp_path / "output")])
        captured = capsys.readouterr()
        assert exit_code != 0
        assert "Traceback" not in captured.err
        assert "permission denied" in captured.err.lower()
    finally:
        input_path.chmod(0o644)  # restore so pytest's tmp_path cleanup can remove it
