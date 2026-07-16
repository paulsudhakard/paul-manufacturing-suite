"""ResolutionException branch — category: internal or validation (TDD §18).

TDD §18 lists the parent's category ambiguously as "internal or
validation" and leaves the split to whoever implements it. Smallest
decision consistent with the rest of the TDD (per its own §"Summary"
precedent for exactly this kind of gap):

- RuleResolutionException: conflicting overrides or a missing rule
  category is a *data integrity* problem in already-loaded configuration,
  not a problem with a particular request's input → internal.
- ProductDefinitionLoadException: TDD §6 is explicit that a
  ProductDefinition "failing schema validation, referencing a
  non-existent rule category, or declaring an unreachable workflow
  state is rejected at registration" — that is squarely a validation
  outcome → validation.

Flagging here (not silently deciding) per Engineering Rule 10: elevate
this to an explicit TDD amendment if a future sprint disagrees.
"""

from __future__ import annotations

from core.exceptions.base import PlatformException
from core.exceptions.categories import INTERNAL, VALIDATION


class ResolutionException(PlatformException):
    """Base for rule/definition resolution failures."""

    category = INTERNAL


class RuleResolutionException(ResolutionException):
    """Conflicting rule overrides, or a referenced rule category is missing."""

    category = INTERNAL


class ProductDefinitionLoadException(ResolutionException):
    """A ProductDefinition failed schema validation or registration checks."""

    category = VALIDATION
