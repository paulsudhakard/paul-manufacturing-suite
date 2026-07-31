"""Idempotency support for state-mutating endpoints (TDD §4.3): replaying
the same idempotency_key returns the original response rather than
re-executing — necessary because the Adapter has no reliable retry
semantics of its own.

In-memory only for now (no persistence layer exists until Sprint 11) —
acceptable because idempotency only needs to survive short-lived
client-side retries within a single Core process lifetime, not a Core
restart.
"""

from __future__ import annotations

import threading
from typing import Any


class IdempotencyStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._responses: dict[str, tuple[int, dict[str, Any]]] = {}

    def get(self, key: str) -> tuple[int, dict[str, Any]] | None:
        with self._lock:
            return self._responses.get(key)

    def put(self, key: str, status: int, body: dict[str, Any]) -> None:
        with self._lock:
            self._responses[key] = (status, body)
