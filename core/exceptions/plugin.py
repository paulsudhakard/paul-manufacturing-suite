"""PluginException branch — category: plugin_error (TDD §18)."""

from __future__ import annotations

from core.exceptions.base import PlatformException
from core.exceptions.categories import PLUGIN_ERROR


class PluginException(PlatformException):
    """Base for ProductPlugin discovery/registration/execution failures."""

    category = PLUGIN_ERROR


class PluginConformanceException(PluginException):
    """A plugin failed the Conformance Suite's registration checks (TDD §2.3)."""


class PluginRuntimeException(PluginException):
    """Raised during a plugin's validate/analyze/repair/generate_* hooks."""
