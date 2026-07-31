"""PlatformException — the root of the Core exception hierarchy (TDD §18).

Rule (TDD §18): every exception thrown across an engine boundary must be
one of PlatformException's subclasses. A raw/unclassified exception
reaching the API layer is treated as a defect. Sprint 1 establishes the
hierarchy itself; the API-layer catch-all that enforces this rule arrives
with the API in Sprint 2.
"""

from __future__ import annotations

from typing import Any

from core.exceptions.categories import INTERNAL


class PlatformException(Exception):
    """Base of the Core exception hierarchy.

    Attributes:
        message: human-readable, safe to show an operator (TDD §17.2) —
            this is also what `str(exception)` returns.
        category: maps directly to ErrorResponse.category (TDD §17.1).
            Defaults to "internal"; every concrete leaf below overrides
            this with its correct, specific category.
        context: structured extra fields for logging (mirrors
            LogEntry.context, TDD §19), never included in the
            operator-facing message itself.
    """

    category: str = INTERNAL

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context: dict[str, Any] = context or {}

    def __repr__(self) -> str:
        return f"{type(self).__name__}(category={self.category!r}, message={self.message!r})"
