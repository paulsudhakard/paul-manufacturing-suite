"""SecurityException branch — category: security (TDD §18)."""
from __future__ import annotations

from core.exceptions.base import PlatformException
from core.exceptions.categories import SECURITY


class SecurityException(PlatformException):
    """Base for authentication/authorization failures."""

    category = SECURITY


class AuthenticationException(SecurityException):
    """Request is missing or has a mismatching local bearer token (TDD §29)."""


class AuthorizationException(SecurityException):
    """Request is authenticated but the operator role lacks permission (TDD §30)."""
