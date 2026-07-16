import json

import pytest

from core.logging import LogEntry


def test_valid_entry_serializes_to_expected_json_shape():
    entry = LogEntry(
        timestamp="2026-01-01T00:00:00+00:00",
        level="INFO",
        component="core.main",
        message="hello",
        correlation_id="abc",
        job_id=None,
        context={"k": "v"},
    )
    parsed = json.loads(entry.to_json())
    assert parsed == {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "level": "INFO",
        "component": "core.main",
        "correlation_id": "abc",
        "job_id": None,
        "message": "hello",
        "context": {"k": "v"},
    }


def test_invalid_level_rejected():
    with pytest.raises(ValueError):
        LogEntry(timestamp="t", level="NOPE", component="c", message="m")


def test_now_timestamp_is_iso8601_parseable():
    from datetime import datetime

    ts = LogEntry.now_timestamp()
    datetime.fromisoformat(ts)  # raises if not valid ISO8601
