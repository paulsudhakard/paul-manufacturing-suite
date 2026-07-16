"""WorkflowException branch — category: conflict or validation (TDD §18).

Same kind of split decision as ResolutionException (see resolution.py's
docstring) — smallest decision consistent with the rest of the TDD:

- InvalidTransitionException: attempting to advance a WorkflowInstance
  via an event that has no valid transition from its *current* state is
  a conflict between the request and the instance's live state (same
  shape as an HTTP 409) → conflict.
- UnreachableStateException: TDD §8 is explicit this is caught at
  *registration* by structural validation ("every declared state must be
  reachable from initial_state") → validation.
"""

from __future__ import annotations

from core.exceptions.base import PlatformException
from core.exceptions.categories import CONFLICT, VALIDATION


class WorkflowException(PlatformException):
    """Base for workflow state-machine failures."""

    category = CONFLICT


class InvalidTransitionException(WorkflowException):
    """No valid transition exists for this event from the instance's current state."""

    category = CONFLICT


class UnreachableStateException(WorkflowException):
    """A WorkflowDefinition declares a state unreachable from initial_state."""

    category = VALIDATION
