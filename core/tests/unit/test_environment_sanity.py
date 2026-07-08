"""Sprint 0 — Environment Sanity Test.

Acceptance criterion (Implementation Plan, Sprint 0): "A single
'environment sanity' test confirming the Core package imports cleanly
and reports its version."

This is deliberately the only test in Sprint 0. It proves the package
is importable from a fresh clone with no manual sys.path hacking
(see conftest.py) and that it exposes a well-formed version string.
Everything else (engines, API, etc.) arrives in later sprints.
"""
import re

import core


def test_core_package_imports_cleanly():
    """Importing `core` must not raise and must yield a module object."""
    assert core is not None


def test_core_reports_a_version():
    """`core.__version__` must exist and look like a semantic version."""
    assert hasattr(core, "__version__")
    version = core.__version__
    assert isinstance(version, str)
    # semver-ish: MAJOR.MINOR.PATCH, e.g. "0.1.0"
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), (
        f"__version__ {version!r} does not look like a semantic version"
    )
