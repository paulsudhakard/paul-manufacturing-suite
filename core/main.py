"""Core entrypoint. No HTTP layer yet (arrives Sprint 2) — this proves the
skeleton (config, logging, exception hierarchy, event bus) works standalone.

Run with:  python3 -m core.main   (or the `pms-core` console script)
"""
from __future__ import annotations

import sys
import uuid

import core
from core.config import ConfigLoader, CoreConfig
from core.events import Event, EventBus, make_logging_subscriber
from core.exceptions import ALL_LEAF_EXCEPTIONS, PlatformException
from core.logging import LogWriter


def _run_exception_self_test(log_writer: LogWriter) -> int:
    """Raise and log one instance of every leaf exception, confirming each
    is caught as a PlatformException and reports its correct category.
    Returns the count verified. Raises AssertionError on any mismatch —
    a startup-time contract violation, not something to silently log past.
    """
    verified = 0
    for exc_class in ALL_LEAF_EXCEPTIONS:
        correlation_id = str(uuid.uuid4())
        try:
            raise exc_class(f"self-test: forced {exc_class.__name__}")
        except PlatformException as exc:
            assert exc.category == exc_class.category, (
                f"{exc_class.__name__} logged category {exc.category!r}, "
                f"expected {exc_class.category!r}"
            )
            log_writer.log(
                "ERROR",
                exc.message,
                component="exception_self_test",
                correlation_id=correlation_id,
                context={"exception_type": exc_class.__name__, "category": exc.category},
            )
            verified += 1
    return verified


def main() -> int:
    config: CoreConfig = ConfigLoader.load(config_path="config.yaml")
    log_writer = LogWriter(
        log_dir=config.logging.log_dir,
        retention_days=config.logging.retention_days,
    )
    event_bus = EventBus()
    event_bus.subscribe("core.started", make_logging_subscriber(log_writer))
    event_bus.subscribe("core.self_test.completed", make_logging_subscriber(log_writer))

    try:
        log_writer.log(
            "INFO",
            f"PMS Core v{core.__version__} starting",
            component="core.main",
            context={"bind_host": config.api.bind_host, "port": config.api.port},
        )
        event_bus.publish(Event("core.started", {"version": core.__version__}))

        verified = _run_exception_self_test(log_writer)
        event_bus.publish(Event("core.self_test.completed", {"exceptions_verified": verified}))

        log_writer.log(
            "INFO",
            f"Exception hierarchy self-test passed: {verified} exception types verified",
            component="core.main",
        )
        log_writer.log("INFO", "PMS Core shutting down cleanly", component="core.main")
        return 0
    finally:
        log_writer.close()


if __name__ == "__main__":
    sys.exit(main())
