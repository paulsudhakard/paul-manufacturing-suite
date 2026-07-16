import pytest

from core.exceptions import (
    ALL_LEAF_EXCEPTIONS,
    CONFLICT,
    INTERNAL,
    NOT_FOUND,
    PLUGIN_ERROR,
    SECURITY,
    VALIDATION,
    PlatformException,
)

EXPECTED_CATEGORIES = {
    "GeometryFormatException": VALIDATION,
    "RuleThresholdViolation": VALIDATION,
    "RuleResolutionException": INTERNAL,
    "ProductDefinitionLoadException": VALIDATION,
    "PluginConformanceException": PLUGIN_ERROR,
    "PluginRuntimeException": PLUGIN_ERROR,
    "MachineCompatibilityException": VALIDATION,
    "MaterialCompatibilityException": VALIDATION,
    "InvalidTransitionException": CONFLICT,
    "UnreachableStateException": VALIDATION,
    "AuthenticationException": SECURITY,
    "AuthorizationException": SECURITY,
    "JobNotFoundException": NOT_FOUND,
    "VersionConflictException": CONFLICT,
}


def test_every_leaf_exception_has_an_expected_category_mapping():
    assert {c.__name__ for c in ALL_LEAF_EXCEPTIONS} == set(EXPECTED_CATEGORIES)


@pytest.mark.parametrize("exc_class", list(ALL_LEAF_EXCEPTIONS), ids=lambda c: c.__name__)
def test_leaf_exception_reports_correct_category(exc_class):
    instance = exc_class("boom")
    assert instance.category == EXPECTED_CATEGORIES[exc_class.__name__]
    assert isinstance(instance, PlatformException)


def test_exception_carries_message_and_context():
    exc = PlatformException("something failed", context={"job_id": "abc"})
    assert exc.message == "something failed"
    assert str(exc) == "something failed"
    assert exc.context == {"job_id": "abc"}


def test_default_platform_exception_category_is_internal():
    assert PlatformException("boom").category == INTERNAL
