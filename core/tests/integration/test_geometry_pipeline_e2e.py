"""End-to-end: CorelDRAW (simulated) -> Export Geometry -> Send to Core ->
Validate -> Return Response -> CorelDRAW receives successful result.

Runs a real Core server (ThreadingWSGIServer) in a background thread and
drives it with the reference Adapter client over real HTTP to 127.0.0.1
— nothing here is mocked at the network layer.
"""

import threading
import time

import pytest

from adapters.coreldraw.reference_client import CoreClient, simulate_export
from core.api.server import build_server
from core.config import ConfigLoader
from core.exceptions import GeometryFormatException
from core.geometry import assert_round_trip, geometry_from_dict
from core.logging import LogWriter


@pytest.fixture
def running_core(tmp_path):
    config = ConfigLoader.load(
        config_path=tmp_path / "none.yaml",
        env={"PMS_API_PORT": "0", "PMS_API_AUTH_TOKEN_PATH": str(tmp_path / "token")},
    )
    log_writer = LogWriter(tmp_path / "logs", echo_stdout=False)
    server, token = build_server(config, log_writer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    try:
        yield server.port, token
    finally:
        server.shutdown()
        server.server_close()
        log_writer.close()


def test_full_pipeline_success(running_core):
    port, token = running_core
    client = CoreClient(auth_token=token, port=port)

    assert client.health()["status"] == "ok"

    exported_geometry = simulate_export()
    result = client.submit_job(product_type="emboss_seal", geometry=exported_geometry)

    assert result.status == "received"
    assert result.job_id

    # "CorelDRAW receives successful result" -- and the geometry it gets
    # back round-trips against what it sent, within TDD §5.4's epsilon.
    original = geometry_from_dict(exported_geometry)
    returned = geometry_from_dict(result.geometry)
    assert_round_trip(original, returned, epsilon=0.001)


def test_malformed_geometry_returns_structured_error(running_core):
    port, token = running_core
    client = CoreClient(auth_token=token, port=port)

    with pytest.raises(GeometryFormatException) as exc_info:
        client.submit_job(product_type="emboss_seal", geometry={"units": "mm"})

    assert exc_info.value.category == "validation"
    assert "correlation_id" in exc_info.value.context


def test_idempotent_resubmission_returns_same_job(running_core):
    port, token = running_core
    client = CoreClient(auth_token=token, port=port)

    key = "fixed-idempotency-key-1"
    first = client.submit_job(
        product_type="emboss_seal", geometry=simulate_export(), idempotency_key=key
    )
    second = client.submit_job(
        product_type="emboss_seal", geometry=simulate_export(), idempotency_key=key
    )

    assert first.job_id == second.job_id  # not a duplicate job


def test_unauthenticated_request_rejected(running_core):
    import requests

    port, _token = running_core
    response = requests.get(f"http://127.0.0.1:{port}/v1/health", timeout=5)
    assert response.status_code == 401


def test_client_retries_transient_failure_then_succeeds(running_core, monkeypatch):
    port, token = running_core
    client = CoreClient(auth_token=token, port=port, max_retries=3, backoff_seconds=0.01)

    real_request = client._session.request
    calls = {"n": 0}

    def flaky(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 2:
            import requests as requests_module

            raise requests_module.exceptions.ConnectionError("simulated transient failure")
        return real_request(*args, **kwargs)

    monkeypatch.setattr(client._session, "request", flaky)

    body = client.health()
    assert body["status"] == "ok"
    assert calls["n"] == 2  # failed once, retried, succeeded
