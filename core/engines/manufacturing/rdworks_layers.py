"""RDWorks-compatible layer/color mapping.

RDWorks (and most laser-control software) assigns cutting/engraving
parameters *by DXF layer color*, not by layer name. This module is the
single place that decides which color index means what — a first-draft
convention (like every other unvalidated constant in this project) that
needs a real RDWorks operator's confirmation before being trusted as
final for production. AutoCAD Color Index (ACI) values used below:
1=red, 2=yellow, 3=green, 5=blue, 6=magenta, 7=white/black.
"""
from __future__ import annotations

from core.engines.geometry.io.dxf_io import DxfLayer
from core.engines.geometry.model import CompoundPath, as_compound
from core.engines.manufacturing.male_female import MaleFemaleResult
from core.engines.manufacturing.preview import ManufacturingPreview

LAYER_COLOR_MAP: dict[str, int] = {
    "ORIGINAL": 7,
    "REPAIRED": 7,
    "MALE_CUT": 1,
    "FEMALE_CUT": 3,
    "RELIEF": 2,
    "REGISTRATION": 5,
    "ALIGNMENT": 6,
}


def _shapes_to_compound(shapes: tuple) -> CompoundPath:
    paths = []
    for s in shapes:
        paths.extend(as_compound(s).paths)
    return CompoundPath(tuple(paths))


def preview_to_dxf_layers(preview: ManufacturingPreview) -> list[DxfLayer]:
    """Maps a ManufacturingPreview bundle onto RDWorks-ready DXF layers.
    Includes every stage so a human can inspect the whole bundle in one
    file during setup/QA; a real production cut would export only
    male_die_production_layers or female_die_production_layers instead.
    """
    return [
        DxfLayer("ORIGINAL", LAYER_COLOR_MAP["ORIGINAL"], preview.original),
        DxfLayer("REPAIRED", LAYER_COLOR_MAP["REPAIRED"], preview.repaired),
        DxfLayer("MALE_CUT", LAYER_COLOR_MAP["MALE_CUT"], preview.male),
        DxfLayer("FEMALE_CUT", LAYER_COLOR_MAP["FEMALE_CUT"], preview.female),
        DxfLayer("RELIEF", LAYER_COLOR_MAP["RELIEF"], preview.relief),
        DxfLayer(
            "REGISTRATION",
            LAYER_COLOR_MAP["REGISTRATION"],
            _shapes_to_compound(preview.registration),
        ),
        DxfLayer(
            "ALIGNMENT", LAYER_COLOR_MAP["ALIGNMENT"], _shapes_to_compound(preview.alignment)
        ),
    ]


def male_die_production_layers(male_female: MaleFemaleResult) -> list[DxfLayer]:
    """The layer set for an actual production cut of the Male die."""
    return [
        DxfLayer("MALE_CUT", LAYER_COLOR_MAP["MALE_CUT"], male_female.male),
        DxfLayer(
            "REGISTRATION",
            LAYER_COLOR_MAP["REGISTRATION"],
            _shapes_to_compound(male_female.registration),
        ),
        DxfLayer(
            "ALIGNMENT", LAYER_COLOR_MAP["ALIGNMENT"], _shapes_to_compound(male_female.alignment)
        ),
    ]


def female_die_production_layers(male_female: MaleFemaleResult) -> list[DxfLayer]:
    return [
        DxfLayer("FEMALE_CUT", LAYER_COLOR_MAP["FEMALE_CUT"], male_female.female),
        DxfLayer(
            "REGISTRATION",
            LAYER_COLOR_MAP["REGISTRATION"],
            _shapes_to_compound(male_female.registration),
        ),
        DxfLayer(
            "ALIGNMENT", LAYER_COLOR_MAP["ALIGNMENT"], _shapes_to_compound(male_female.alignment)
        ),
    ]
