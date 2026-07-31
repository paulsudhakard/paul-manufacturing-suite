"""LogEntry — the structured log record shape (TDD §19)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

VALID_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


@dataclass(frozen=True)
class LogEntry:
    """Matches TDD §19's LogEntry schema exactly.

    `context` carries structured, engine-specific extra fields — this is
    where an exception's own `.context` (core/exceptions/base.py) or a
    Sprint-1-self-test's exception details end up when logged.
    """

    timestamp: str
    level: str
    component: str
    message: str
    correlation_id: str | None = None
    job_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.level not in VALID_LEVELS:
            raise ValueError(f"LogEntry.level must be one of {VALID_LEVELS}, got {self.level!r}")

    @staticmethod
    def now_timestamp() -> str:
        """ISO8601 timestamp, UTC, matching TDD §19's `timestamp: ISO8601`."""
        return datetime.now(timezone.utc).isoformat()

    def to_json(self) -> str:
        """Single-line JSON, for one-log-entry-per-line file output."""
        return json.dumps(
            {
                "timestamp": self.timestamp,
                "level": self.level,
                "component": self.component,
                "correlation_id": self.correlation_id,
                "job_id": self.job_id,
                "message": self.message,
                "context": self.context,
            },
            default=str,
        )
