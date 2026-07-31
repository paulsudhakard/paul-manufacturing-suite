"""EventBus — in-process publish/subscribe (TDD §32).

Guarantee (TDD §32): at-least-once delivery to subscribers within the
same process; no durability across a crash — the underlying state change
is what's durably persisted, the event is just a notification of that
fact. Deliberately not a message broker (over-engineering at Option A
scale, TDD §32).

Isolation: one subscriber raising must not prevent delivery to the
others, or crash the publisher — mirrors the plugin-registration-failure
isolation principle established elsewhere (TDD §2.3).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

from core.events.event import Event

Handler = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: Handler) -> None:
        self._subscribers[event_type].append(handler)

    def publish(self, event: Event) -> list[Exception]:
        """Deliver to every subscriber of event.event_type.

        Returns any exceptions raised by subscribers (rather than raising
        them) so one bad handler can't block delivery to the rest or crash
        the publisher; callers that care can log/inspect them.
        """
        errors: list[Exception] = []
        for handler in self._subscribers.get(event.event_type, []):
            try:
                handler(event)
            except Exception as exc:  # noqa: BLE001 — isolation is the point
                errors.append(exc)
        return errors
