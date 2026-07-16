"""A deliberately minimal, in-memory Job record — just enough to give
POST /v1/jobs somewhere to put an accepted submission and hand back a
job_id.

This is NOT TDD §12's full Job schema (versions_used, workflow_instance_ref,
geometry_refs-as-pointers, SQLite persistence, etc.) — those depend on the
Workflow Engine and Rule Engine, which don't exist yet. Building the full
schema now against nothing would mean guessing at fields that later
sprints will define for real. This interim record is intentionally
small and explicitly named as interim so it's obvious what it isn't.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from core.geometry import NeutralGeometry


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    product_type: str
    status: str  # "received" this chunk — real workflow states arrive with the Workflow Engine
    geometry: NeutralGeometry
    created_at: str


class InMemoryJobStore:
    """Thread-safe. In-memory only — real persistence is Sprint 11's job."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, JobRecord] = {}

    def create(self, product_type: str, geometry: NeutralGeometry) -> JobRecord:
        record = JobRecord(
            job_id=str(uuid.uuid4()),
            product_type=product_type,
            status="received",
            geometry=geometry,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._jobs[record.job_id] = record
        return record

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)
