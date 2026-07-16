"""The Adapter <-> NeutralGeometry contract (TDD §5.4, Architecture v3
§2.3). Any CAD/UI Adapter (CorelDRAW today; others admitted later
without Core changes) implements this shape on its own side — in VBA
for CorelDRAW (adapters/coreldraw/src/CadIO/clsGeometrySerializer.cls,
Sprint 4's original scope, not re-implemented here) — while Core only
needs to know the *contract*, expressed here as a Protocol so type
checkers can verify conformance without runtime inheritance.
"""

from __future__ import annotations

from typing import Protocol

from core.geometry.models import NeutralGeometry


class GeometryAdapter(Protocol):
    """What Core expects of any CAD/UI Adapter's geometry boundary."""

    def shape_to_neutral(self, native_shape: object) -> NeutralGeometry:
        """Serialize a native CAD shape into NeutralGeometry."""
        ...

    def neutral_to_shape(self, geometry: NeutralGeometry) -> object:
        """Materialize NeutralGeometry back into a native CAD shape."""
        ...
