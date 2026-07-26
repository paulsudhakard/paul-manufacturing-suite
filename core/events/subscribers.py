"""Event Bus subscribers. Sprint 1 ships exactly one: logging."""
from __future__ import annotations

from typing import Callable

from core.events.event import Event
from core.logging import LogWriter


def make_logging_subscriber(log_writer: LogWriter) -> Callable[[Event], None]:
    """Every event is logged at INFO minimum (TDD §32)."""

    def _on_event(event: Event) -> None:
        log_writer.log(
            "INFO",
            f"event: {event.event_type}",
            component="event_bus",
            context={"event_type": event.event_type, "payload": event.payload},
        )

    return _on_event
