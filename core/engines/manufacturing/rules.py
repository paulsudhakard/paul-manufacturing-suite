"""Manufacturing Rule Engine. Every threshold the Manufacturing Validator,
Repair, and Male/Female Generator use comes from a `RuleSet` loaded here
— never a literal embedded in algorithm code. `RuleSet.load_default()`
reads `config/default_rules.yaml`; production use should call
`RuleSet.load(path)` against a real, reviewed configuration file.

Not the full Knowledge Engine (TDD §12, §12.2-12.3's product/material/
machine override resolution) — that's explicitly out of scope here (no
plugin framework). This is a flat, single-tier configuration: one
RuleSet, all values, loaded once. Extending it to multi-tier resolution
later is a natural, additive extension of this same shape.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

import yaml

_DEFAULT_CONFIG_PATH = Path(__file__).parent / "config" / "default_rules.yaml"


@dataclass(frozen=True)
class RuleSet:
    min_line_width_mm: float
    min_bridge_width_mm: float
    min_spacing_mm: float
    min_enclosed_area_mm2: float
    max_node_density_per_mm: float
    min_text_height_mm: float
    corner_radius_mm: float
    clearance_mm: float
    kerf_compensation_mm: float
    paper_deformation_allowance_mm: float
    material_compensation_mm: float
    sharp_corner_angle_threshold_degrees: float
    island_merge_search_radius_mm: float
    flatten_tolerance_mm: float
    registration_mark_diameter_mm: float
    registration_mark_margin_mm: float
    alignment_mark_size_mm: float
    alignment_mark_margin_mm: float
    relief_depth_mm: float

    @staticmethod
    def load(path: Path | str) -> "RuleSet":
        data = yaml.safe_load(Path(path).read_text()) or {}
        required = {f.name for f in fields(RuleSet)}
        missing = required - data.keys()
        if missing:
            raise ValueError(
                f"Manufacturing rule config {path} is missing required keys: {sorted(missing)}"
            )
        extra = data.keys() - required
        if extra:
            raise ValueError(
                f"Manufacturing rule config {path} has unknown keys: {sorted(extra)}"
            )
        return RuleSet(**{k: float(v) for k, v in data.items()})

    @staticmethod
    def load_default() -> "RuleSet":
        return RuleSet.load(_DEFAULT_CONFIG_PATH)
