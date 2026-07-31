"""The full Core exception hierarchy (TDD §18), assembled from one module
per branch for readability. Import from `core.exceptions` directly:

    from core.exceptions import PluginConformanceException

Every exception here derives from PlatformException and carries a
`category` attribute matching TDD §17.1's ErrorResponse.category values.
"""

from core.exceptions.base import PlatformException
from core.exceptions.categories import (
    CONFLICT,
    INTERNAL,
    NOT_FOUND,
    PLUGIN_ERROR,
    SECURITY,
    VALIDATION,
)
from core.exceptions.compatibility import (
    CompatibilityException,
    MachineCompatibilityException,
    MaterialCompatibilityException,
)
from core.exceptions.persistence import (
    JobNotFoundException,
    PersistenceException,
    VersionConflictException,
)
from core.exceptions.plugin import (
    PluginConformanceException,
    PluginException,
    PluginRuntimeException,
)
from core.exceptions.resolution import (
    ProductDefinitionLoadException,
    ResolutionException,
    RuleResolutionException,
)
from core.exceptions.security import (
    AuthenticationException,
    AuthorizationException,
    SecurityException,
)
from core.exceptions.validation import (
    GeometryFormatException,
    RuleThresholdViolation,
    ValidationException,
)
from core.exceptions.workflow import (
    InvalidTransitionException,
    UnreachableStateException,
    WorkflowException,
)

__all__ = [
    # base
    "PlatformException",
    # categories
    "VALIDATION",
    "NOT_FOUND",
    "CONFLICT",
    "SECURITY",
    "INTERNAL",
    "PLUGIN_ERROR",
    # validation
    "ValidationException",
    "GeometryFormatException",
    "RuleThresholdViolation",
    # resolution
    "ResolutionException",
    "RuleResolutionException",
    "ProductDefinitionLoadException",
    # plugin
    "PluginException",
    "PluginConformanceException",
    "PluginRuntimeException",
    # compatibility
    "CompatibilityException",
    "MachineCompatibilityException",
    "MaterialCompatibilityException",
    # workflow
    "WorkflowException",
    "InvalidTransitionException",
    "UnreachableStateException",
    # security
    "SecurityException",
    "AuthenticationException",
    "AuthorizationException",
    # persistence
    "PersistenceException",
    "JobNotFoundException",
    "VersionConflictException",
]

# Every leaf (non-base) exception class in the hierarchy — used by the
# Sprint 1 self-test (core/main.py) and its corresponding unit test to
# confirm each one reports the correct category. "Leaf" here means a
# concrete exception meant to actually be raised, not a category base.
ALL_LEAF_EXCEPTIONS: tuple[type[PlatformException], ...] = (
    GeometryFormatException,
    RuleThresholdViolation,
    RuleResolutionException,
    ProductDefinitionLoadException,
    PluginConformanceException,
    PluginRuntimeException,
    MachineCompatibilityException,
    MaterialCompatibilityException,
    InvalidTransitionException,
    UnreachableStateException,
    AuthenticationException,
    AuthorizationException,
    JobNotFoundException,
    VersionConflictException,
)
