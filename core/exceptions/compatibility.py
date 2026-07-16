"""CompatibilityException branch — category: validation (TDD §18)."""

from __future__ import annotations

from core.exceptions.base import PlatformException
from core.exceptions.categories import VALIDATION


class CompatibilityException(PlatformException):
    """Base for machine/material compatibility failures."""

    category = VALIDATION


class MachineCompatibilityException(CompatibilityException):
    """The active Machine Profile is not compatible with this product/job."""


class MaterialCompatibilityException(CompatibilityException):
    """The active Material Profile is not compatible with this product/job."""
