"""Error categories, matching TDD §17.1's ErrorResponse envelope exactly.

Kept as plain string constants (not an enum) because the API layer's
ErrorResponse.category (TDD §17.1) is itself a plain string over the
wire — using the same literal values here means no translation layer
is needed when Sprint 2 builds the ErrorResponseFormatter.
"""

VALIDATION = "validation"
NOT_FOUND = "not_found"
CONFLICT = "conflict"
SECURITY = "security"
INTERNAL = "internal"
PLUGIN_ERROR = "plugin_error"

ALL_CATEGORIES = frozenset(
    {VALIDATION, NOT_FOUND, CONFLICT, SECURITY, INTERNAL, PLUGIN_ERROR}
)
