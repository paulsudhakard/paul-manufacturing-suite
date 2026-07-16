"""ErrorResponse envelope (TDD §17.1) and the PlatformException -> HTTP
mapping (TDD §17.2). error_code is the stable, machine-readable contract
the Adapter programs against; message is display-only and may be
reworded across versions without being a breaking change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from core.exceptions import (
    CONFLICT,
    INTERNAL,
    NOT_FOUND,
    PLUGIN_ERROR,
    SECURITY,
    VALIDATION,
    AuthenticationException,
    AuthorizationException,
    GeometryFormatException,
    PlatformException,
)

# Explicit, stable codes for exceptions this chunk actually raises.
# Anything else falls back to a deterministic CamelCase -> SCREAMING_SNAKE
# derivation (still stable, just not hand-picked) — extend this map as
# each exception type gets its first real caller, per TDD §17.2's own
# "stable once shipped" rule.
_ERROR_CODE_OVERRIDES: dict[type[PlatformException], str] = {
    GeometryFormatException: "GEOMETRY_FORMAT_INVALID",
    AuthenticationException: "AUTHENTICATION_FAILED",
    AuthorizationException: "AUTHORIZATION_FAILED",
}

_CATEGORY_TO_STATUS = {
    VALIDATION: 400,
    NOT_FOUND: 404,
    CONFLICT: 409,
    SECURITY: 403,  # narrowed to 401 for AuthenticationException specifically, below
    INTERNAL: 500,
    PLUGIN_ERROR: 502,
}


def _derive_error_code(exc_type: type[PlatformException]) -> str:
    name = exc_type.__name__.removesuffix("Exception")
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.upper()


def error_code_for(exc: PlatformException) -> str:
    return _ERROR_CODE_OVERRIDES.get(type(exc), _derive_error_code(type(exc)))


def http_status_for(exc: PlatformException) -> int:
    if isinstance(exc, AuthenticationException):
        return 401
    return _CATEGORY_TO_STATUS.get(exc.category, 500)


@dataclass(frozen=True)
class ErrorResponse:
    correlation_id: str
    error_code: str
    category: str
    message: str
    details: list[dict[str, Any]] | None = None
    retryable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "error_code": self.error_code,
            "category": self.category,
            "message": self.message,
            "details": self.details,
            "retryable": self.retryable,
        }

    @staticmethod
    def from_exception(exc: PlatformException, correlation_id: str) -> "ErrorResponse":
        details = None
        issues = exc.context.get("issues") if isinstance(exc.context, dict) else None
        if issues:
            details = [{"field": None, "issue": issue} for issue in issues]
        return ErrorResponse(
            correlation_id=correlation_id,
            error_code=error_code_for(exc),
            category=exc.category,
            message=exc.message,
            details=details,
            retryable=exc.category == INTERNAL,
        )

    @staticmethod
    def internal_error(correlation_id: str) -> "ErrorResponse":
        """The catch-all for an unclassified exception reaching the API
        boundary (TDD §18: "treated as a defect... never a stack trace
        to the Adapter").
        """
        return ErrorResponse(
            correlation_id=correlation_id,
            error_code="INTERNAL_ERROR",
            category=INTERNAL,
            message="An internal error occurred.",
            details=None,
            retryable=True,
        )
