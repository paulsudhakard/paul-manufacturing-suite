#!/usr/bin/env python3
"""Production command-line runner for the PMS Core manufacturing pipeline.

This tool is a thin wrapper around the existing, unmodified orchestrator
(core.orchestration.orchestrator.run) -- it does not implement, extend,
or duplicate any geometry, manufacturing, validation, repair, or DXF
logic. Its only jobs are: read the input SVG, call the orchestrator,
print progress as it reports each stage, and write out the two
artifacts the orchestrator already produces (result.dxf_text and
result.validation_report).

Usage:
    python tools/run_svg_pipeline.py --input logo.svg --output output_dir [--debug]

See docs/ORCHESTRATOR_SEQUENCE.md for what the orchestrator itself does
at each of the 10 stages.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

# Allow running as `python tools/run_svg_pipeline.py` directly (without
# installing the package or setting PYTHONPATH by hand) by putting the
# repository root on sys.path -- same convention already used by every
# other `python -m core.xxx` entry point in this repo.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core.config import ConfigLoader  # noqa: E402
from core.exceptions import PlatformException  # noqa: E402
from core.logging import LogWriter  # noqa: E402
from core.orchestration.orchestrator import OrchestratorResult  # noqa: E402
from core.orchestration.orchestrator import run as run_orchestrator  # noqa: E402

# The fixed, ordered set of internal stage names the orchestrator's
# on_progress callback reports (see core/orchestration/orchestrator.py's
# `report(...)` calls) -- this is the callback's stable contract, not
# duplicated logic; the same list is independently used by
# core/validation_suite/production_validation.py for the same reason.
_STAGE_ORDER = [
    "svg_import",
    "geometry_validation",
    "geometry_repair",
    "manufacturing_validation",
    "manufacturing_repair",
    "male_generator",
    "female_generator",
    "preview_generator",
    "dxf_export",
    "validation_report",
]

_STAGE_LABELS = [
    "SVG Import",
    "Geometry Validation",
    "Geometry Repair",
    "Manufacturing Validation",
    "Manufacturing Repair",
    "Male Generator",
    "Female Generator",
    "Preview Generation",
    "DXF Export",
    "Validation Report",
]


class CliError(Exception):
    """A user-facing error: message is safe to print without a traceback."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_svg_pipeline.py",
        description=(
            "Run the PMS Core manufacturing pipeline against a single SVG file\n"
            "via the existing orchestrator (core.orchestration.orchestrator.run).\n"
            "This tool only invokes that orchestrator -- it does not implement or\n"
            "modify any geometry or manufacturing logic itself."
        ),
        epilog=(
            "Example:\n"
            "  python tools/run_svg_pipeline.py --input test_data/logo.svg --output output\n"
            "\n"
            "Files written to the --output directory:\n"
            "  pipeline.dxf            RDWorks-ready DXF text (result.dxf_text)\n"
            "  validation_report.json  Geometry/manufacturing issues, repair actions,\n"
            "                          and pass/fail (result.validation_report)\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", required=True, type=Path, help="Path to the input SVG file")
    parser.add_argument(
        "--output", required=True, type=Path, help="Output directory (created if missing)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print a full stack trace on error instead of a short, user-friendly message",
    )
    return parser


def _validate_input_path(input_path: Path) -> None:
    if not input_path.exists():
        raise CliError(f"Input file not found: {input_path}")
    if not input_path.is_file():
        raise CliError(f"Input path is not a file: {input_path}")
    if input_path.suffix.lower() != ".svg":
        raise CliError(f"Input file is not an SVG file (expected a .svg extension): {input_path}")


def _read_svg_text(input_path: Path) -> str:
    try:
        return input_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise CliError(f"Input file not found: {input_path}") from exc
    except UnicodeDecodeError as exc:
        raise CliError(
            f"Input file is not valid UTF-8 text, so it cannot be an SVG file: {input_path}"
        ) from exc


def _make_progress_printer(log_writer: LogWriter):
    def on_progress(stage: str) -> None:
        try:
            index = _STAGE_ORDER.index(stage)
        except ValueError:
            index = None
        if index is not None:
            print(f"[{index + 1}/{len(_STAGE_LABELS)}] {_STAGE_LABELS[index]}")
        log_writer.log("INFO", f"Pipeline stage: {stage}", component="tools.run_svg_pipeline")

    return on_progress


def _serialize_preview_if_supported(
    preview: object, output_dir: Path, log_writer: LogWriter
) -> None:
    """Per the runner's scope: only save the preview if the existing
    preview object already supports serialization. No serializer is
    invented here.
    """
    for method_name in ("to_dict", "to_json", "serialize"):
        method = getattr(preview, method_name, None)
        if callable(method):
            data = method()
            preview_path = output_dir / "preview.json"
            preview_path.write_text(
                json.dumps(data, indent=2, default=str) if not isinstance(data, str) else data,
                encoding="utf-8",
            )
            log_writer.log(
                "INFO",
                f"Preview serialized via {method_name}()",
                component="tools.run_svg_pipeline",
            )
            return
    print("Preview serialization is not implemented.")


def _print_summary(
    result: OrchestratorResult, dxf_path: Path, report_path: Path, elapsed_seconds: float
) -> None:
    print()
    print("Pipeline completed successfully.")
    print()
    print("Geometry Issues Before Repair:")
    print(len(result.geometry_issues_before))
    print()
    print("Geometry Repair Actions:")
    print(len(result.geometry_repair_actions))
    print()
    print("Manufacturing Warnings Before Repair:")
    print(len(result.manufacturing_warnings_before))
    print()
    print("Manufacturing Warnings After Repair:")
    print(len(result.manufacturing_warnings_after))
    print()
    print("Pipeline Passed:")
    print(result.validation_report.get("passed"))
    print()
    print("DXF:")
    print(dxf_path)
    print()
    print("Validation Report:")
    print(report_path)
    print()
    print("Execution Time:")
    print(f"{elapsed_seconds:.3f}")


def run_cli(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    input_path: Path = args.input
    output_dir: Path = args.output
    debug: bool = args.debug

    try:
        _validate_input_path(input_path)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except (FileExistsError, NotADirectoryError) as exc:
            raise CliError(f"Output path exists and is not a directory: {output_dir}") from exc
    except CliError as exc:
        # No LogWriter exists yet at this point, by design -- see the
        # log_dir comment below for why. Nothing has "started" yet, so
        # there's nothing worth logging beyond what's already printed here.
        print(f"Error: {exc}", file=sys.stderr)
        if debug:
            traceback.print_exc()
        return exc.exit_code

    # --output is now confirmed to be a real, writable directory, so it's
    # safe (and, per the comment below, important) to scope logging to it
    # rather than to a shared global location.
    config = ConfigLoader.load(config_path="config.yaml")
    log_writer = LogWriter(
        log_dir=output_dir / "logs",
        retention_days=config.logging.retention_days,
        component_default="tools.run_svg_pipeline",
        echo_stdout=False,
    )

    try:
        svg_text = _read_svg_text(input_path)

        log_writer.log(
            "INFO", f"Starting pipeline run for {input_path}", component="tools.run_svg_pipeline"
        )

        start = time.perf_counter()
        result = run_orchestrator(
            svg_text=svg_text,
            source_file_hint=str(input_path),
            on_progress=_make_progress_printer(log_writer),
        )
        elapsed = time.perf_counter() - start

        dxf_path = output_dir / "pipeline.dxf"
        dxf_path.write_text(result.dxf_text, encoding="utf-8")

        report_path = output_dir / "validation_report.json"
        report_path.write_text(json.dumps(result.validation_report, indent=2), encoding="utf-8")

        _serialize_preview_if_supported(result.preview, output_dir, log_writer)

        _print_summary(result, dxf_path, report_path, elapsed)

        log_writer.log(
            "INFO",
            f"Pipeline run completed successfully in {elapsed:.3f}s",
            component="tools.run_svg_pipeline",
            context={"passed": result.validation_report.get("passed")},
        )
        return 0

    except CliError as exc:
        log_writer.log("ERROR", str(exc), component="tools.run_svg_pipeline")
        print(f"Error: {exc}", file=sys.stderr)
        if debug:
            traceback.print_exc()
        return exc.exit_code

    except PermissionError as exc:
        log_writer.log("ERROR", f"Permission denied: {exc}", component="tools.run_svg_pipeline")
        print(f"Error: Permission denied: {exc.filename or exc}", file=sys.stderr)
        if debug:
            traceback.print_exc()
        return 1

    except PlatformException as exc:
        log_writer.log(
            "ERROR",
            exc.message,
            component="tools.run_svg_pipeline",
            context={"category": exc.category},
        )
        print(f"Error: {exc.message}", file=sys.stderr)
        if debug:
            traceback.print_exc()
        return 1

    except Exception as exc:  # noqa: BLE001 -- last-resort, user-friendly by default
        log_writer.log("ERROR", f"Unexpected error: {exc!r}", component="tools.run_svg_pipeline")
        print(f"Error: an unexpected error occurred ({type(exc).__name__}: {exc})", file=sys.stderr)
        if debug:
            traceback.print_exc()
        return 1

    finally:
        log_writer.close()


def main(argv: list[str] | None = None) -> int:
    return run_cli(argv)


if __name__ == "__main__":
    sys.exit(main())
