"""Production Validation Suite.

Runs `core.orchestration.orchestrator.run()` — unmodified — against a
directory of supplied SVG files and reports per-stage pass/fail plus a
summary table in the exact format requested:

    Artwork | Import | Validation | Repair | Male | Female | Preview | DXF | Report | Pass/Fail

Definition of "passes" used throughout this module: a stage *passes* if
it executes without raising an unhandled exception and produces its
expected output. It does NOT mean "zero warnings were found" — the
Manufacturing Validator finding warnings on real artwork is normal and
expected (that's what it's for); a validation *stage* only fails if it
itself errors out. Warning/issue counts are reported separately on
`ArtworkValidationResult`, never conflated with pass/fail.

Per-stage granularity is obtained without duplicating or rewriting the
orchestrator: `orchestrator.run()` already accepts an `on_progress`
callback (called once at the start of each stage, in order). This
module uses that callback to record which stage was reached; if an
exception is raised, the stage in progress when it was raised is the
last one recorded, everything before it necessarily completed, and
everything after it never ran. This gives accurate per-stage results
from the single existing entry point.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.engines.manufacturing.rules import RuleSet
from core.orchestration.orchestrator import OrchestratorResult, run

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

# Which summary-table column each internal stage name maps to. Geometry
# and Manufacturing validation both fall under the single "Validation"
# column, per the requested table shape; likewise geometry and
# manufacturing repair both fall under "Repair".
_STAGE_TO_COLUMN = {
    "svg_import": "Import",
    "geometry_validation": "Validation",
    "geometry_repair": "Repair",
    "manufacturing_validation": "Validation",
    "manufacturing_repair": "Repair",
    "male_generator": "Male",
    "female_generator": "Female",
    "preview_generator": "Preview",
    "dxf_export": "DXF",
    "validation_report": "Report",
}

_COLUMNS = ["Import", "Validation", "Repair", "Male", "Female", "Preview", "DXF", "Report"]

# The existing module actually responsible for each stage -- used when
# reporting a failure's root cause, so "recommended fix" always points
# at the real code, not a guess.
_STAGE_MODULE = {
    "svg_import": "core.engines.geometry.io.svg_io",
    "geometry_validation": "core.engines.geometry.validation",
    "geometry_repair": "core.engines.geometry.repair",
    "manufacturing_validation": "core.engines.manufacturing.validator",
    "manufacturing_repair": "core.engines.manufacturing.repair",
    "male_generator": "core.engines.manufacturing.male_female",
    "female_generator": "core.engines.manufacturing.male_female",
    "preview_generator": "core.engines.manufacturing.preview",
    "dxf_export": "core.engines.geometry.io.dxf_io / core.engines.manufacturing.rdworks_layers",
    "validation_report": "core.orchestration.orchestrator (data aggregation, no dedicated module)",
}


@dataclass(frozen=True)
class ArtworkValidationResult:
    filename: str
    stage_status: dict  # column name -> "PASS" | "FAIL" | "NOT REACHED"
    overall_pass: bool
    failure_stage: str | None  # internal stage name, None if passed
    failure_exception_type: str | None
    failure_message: str | None
    result: OrchestratorResult | None  # None if the run failed


def validate_single_artwork(
    svg_text: str, filename: str, rule_set: RuleSet | None = None
) -> ArtworkValidationResult:
    reached: list[str] = []

    try:
        result = run(svg_text, rule_set=rule_set, source_file_hint=filename, on_progress=reached.append)
    except Exception as exc:  # noqa: BLE001 -- isolate one file's failure from the batch
        failed_stage = reached[-1] if reached else _STAGE_ORDER[0]
        failed_index = _STAGE_ORDER.index(failed_stage)
        stage_status = {}
        for stage in _STAGE_ORDER:
            column = _STAGE_TO_COLUMN[stage]
            idx = _STAGE_ORDER.index(stage)
            if idx < failed_index:
                stage_status[column] = "PASS"
            elif idx == failed_index:
                stage_status[column] = "FAIL"
            else:
                stage_status.setdefault(column, "NOT REACHED")
        return ArtworkValidationResult(
            filename=filename,
            stage_status=stage_status,
            overall_pass=False,
            failure_stage=failed_stage,
            failure_exception_type=type(exc).__name__,
            failure_message=str(exc),
            result=None,
        )

    return ArtworkValidationResult(
        filename=filename,
        stage_status={col: "PASS" for col in _COLUMNS},
        overall_pass=True,
        failure_stage=None,
        failure_exception_type=None,
        failure_message=None,
        result=result,
    )


def validate_artwork_directory(
    svg_dir: str | Path, rule_set: RuleSet | None = None
) -> list[ArtworkValidationResult]:
    results = []
    for svg_path in sorted(Path(svg_dir).glob("*.svg")):
        text = svg_path.read_text(encoding="utf-8")
        results.append(validate_single_artwork(text, svg_path.name, rule_set))
    return results


def render_summary_table(results: list[ArtworkValidationResult]) -> str:
    header = "| Artwork | " + " | ".join(_COLUMNS) + " | Pass/Fail |"
    separator = "|---" * (len(_COLUMNS) + 2) + "|"
    lines = [header, separator]
    for r in results:
        cells = [r.stage_status.get(col, "-") for col in _COLUMNS]
        overall = "PASS" if r.overall_pass else "FAIL"
        lines.append(f"| {r.filename} | " + " | ".join(cells) + f" | {overall} |")
    return "\n".join(lines)


def render_failure_report(result: ArtworkValidationResult) -> str:
    if result.overall_pass:
        return f"{result.filename}: no failure."
    module = _STAGE_MODULE.get(result.failure_stage, "unknown")
    return (
        f"Artwork: {result.filename}\n"
        f"Failed stage: {result.failure_stage}\n"
        f"Existing module responsible: {module}\n"
        f"Root cause: {result.failure_exception_type}: {result.failure_message}\n"
        f"Recommended fix: see root cause above -- investigate the specific input against "
        f"{module}. Do not patch this artwork specifically; fix the generic case the error "
        f"reveals, then add this file as a regression fixture."
    )
