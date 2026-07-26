"""PersistenceException branch — category: internal, with two more specific
leaf overrides explicitly called out in TDD §18.
"""
from __future__ import annotations

from core.exceptions.base import PlatformException
from core.exceptions.categories import CONFLICT, INTERNAL, NOT_FOUND


class PersistenceException(PlatformException):
    """Base for data-layer failures."""

    category = INTERNAL


class JobNotFoundException(PersistenceException):
    """The requested Job does not exist."""

    category = NOT_FOUND


class VersionConflictException(PersistenceException):
    """Optimistic concurrency conflict on a versioned record (TDD §23)."""

    category = CONFLICT
