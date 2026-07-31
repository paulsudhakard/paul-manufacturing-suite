"""ValidationException branch — category: validation (TDD §18)."""

from __future__ import annotations

from core.exceptions.base import PlatformException
from core.exceptions.categories import VALIDATION


class ValidationException(PlatformException):
    """Base for input/geometry/rule-threshold validation failures."""

    category = VALIDATION


class GeometryFormatException(ValidationException):
    """Malformed Neutral Geometry input (TDD §5, §18)."""


class RuleThresholdViolation(ValidationException):
    """A resolved rule threshold was violated by the input geometry."""
