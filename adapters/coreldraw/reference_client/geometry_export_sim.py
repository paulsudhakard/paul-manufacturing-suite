"""Stands in for the real Adapter-side ShapeToNeutral() (TDD §5.4),
which requires CorelDRAW's COM API and isn't available in this
environment. Produces a fixture NeutralGeometry payload shaped exactly
like what a real export would produce, so the E2E test can exercise
"CorelDRAW -> Export Geometry -> Send to Core" without real CorelDRAW.

Explicitly NOT a claim that real CorelDRAW round-trip fidelity has been
validated — that remains Sprint 3/4's original, real-CorelDRAW-required
acceptance criterion, still outstanding.
"""

from __future__ import annotations

from typing import Any


def simulate_export(source_file_hint: str = "test_seal.cdr") -> dict[str, Any]:
    """A simple closed square path on one layer — enough to exercise the
    full pipeline without needing real artwork or real CorelDRAW.
    """
    return {
        "units": "mm",
        "bounding_box": {"x": 0.0, "y": 0.0, "width": 20.0, "height": 20.0},
        "layers": [
            {
                "layer_role": "original",
                "objects": [
                    {
                        "object_id": "obj-1",
                        "subpaths": [
                            {
                                "closed": True,
                                "nodes": [
                                    {"x": 0.0, "y": 0.0, "node_type": "line"},
                                    {"x": 20.0, "y": 0.0, "node_type": "line"},
                                    {"x": 20.0, "y": 20.0, "node_type": "line"},
                                    {"x": 0.0, "y": 20.0, "node_type": "line"},
                                ],
                            }
                        ],
                        "fill": {"type": "none", "color": None},
                        "stroke": {"width": 0.25},
                    }
                ],
            }
        ],
        "metadata": {
            "source_adapter": "coreldraw",
            "source_file_hint": source_file_hint,
            "imported_at": "2026-01-01T00:00:00+00:00",
        },
    }
