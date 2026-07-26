"""Process starts → loads config → logs a startup line → deliberately
raises and logs one exception of each category → exits cleanly with
code 0 (Sprint 1 acceptance criterion), run in-process rather than via
subprocess for speed — main() itself returns the exit code.
"""
import json

from core.main import main


def test_core_starts_runs_self_test_and_exits_cleanly(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    exit_code = main()
    assert exit_code == 0

    log_file = tmp_path / ".pms" / "logs" / "core.log"
    assert log_file.exists()

    lines = [json.loads(line) for line in log_file.read_text().splitlines() if line.strip()]

    assert any("starting" in entry["message"] for entry in lines if entry["level"] == "INFO")
    assert any("shutting down cleanly" in entry["message"] for entry in lines)

    error_entries = [e for e in lines if e["level"] == "ERROR"]
    assert len(error_entries) == 14  # one per leaf exception, core/exceptions/__init__.py
    for entry in error_entries:
        assert entry["correlation_id"] is not None
        assert "category" in entry["context"]
