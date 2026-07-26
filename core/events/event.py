"""Event — the generic pub/sub payload for the in-process Event Bus (TDD §32)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Event:
    event_type: str  # "noun.past_tense_verb", e.g. "core.started" — TDD §35
    payload: dict[str, Any] = field(default_factory=dict)
    emitted_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
