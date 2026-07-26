"""LogWriter — writes LogEntry records to a local, rotating-by-day file
(TDD §19: "local rotating file (per-day) always"). Retention defaults to
90 days, configurable via CoreConfig.logging.retention_days.
"""
from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from core.logging.log_entry import VALID_LEVELS, LogEntry

_LEVEL_TO_INT = {name: getattr(logging, name) for name in VALID_LEVELS}


class LogWriter:
    """Thin facade over stdlib logging, constrained to emit exactly one
    `LogEntry.to_json()` line per record — every line on disk is valid
    JSON matching TDD §19's schema, with no stdlib formatting noise.
    """

    def __init__(
        self,
        log_dir: Path | str,
        *,
        retention_days: int = 90,
        component_default: str = "core",
        echo_stdout: bool = True,
    ) -> None:
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._component_default = component_default

        self._logger = logging.getLogger(f"pms.core.{id(self)}")
        self._logger.setLevel(logging.DEBUG)
        self._logger.propagate = False
        self._logger.handlers.clear()  # never accumulate across re-construction

        formatter = logging.Formatter("%(message)s")

        file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=self._log_dir / "core.log",
            when="midnight",
            backupCount=retention_days,
            utc=True,
        )
        file_handler.setFormatter(formatter)
        self._logger.addHandler(file_handler)

        if echo_stdout:
            stream_handler = logging.StreamHandler(stream=sys.stdout)
            stream_handler.setFormatter(formatter)
            self._logger.addHandler(stream_handler)

    def write(self, entry: LogEntry) -> None:
        self._logger.log(_LEVEL_TO_INT[entry.level], entry.to_json())

    def log(
        self,
        level: str,
        message: str,
        *,
        component: str | None = None,
        correlation_id: str | None = None,
        job_id: str | None = None,
        context: dict | None = None,
    ) -> LogEntry:
        """Build the LogEntry and write it in one call; returns the entry."""
        entry = LogEntry(
            timestamp=LogEntry.now_timestamp(),
            level=level,
            component=component or self._component_default,
            message=message,
            correlation_id=correlation_id,
            job_id=job_id,
            context=context or {},
        )
        self.write(entry)
        return entry

    def close(self) -> None:
        for handler in list(self._logger.handlers):
            handler.close()
            self._logger.removeHandler(handler)
