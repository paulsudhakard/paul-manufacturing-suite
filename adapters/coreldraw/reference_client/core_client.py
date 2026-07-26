"""Reference implementation of the Adapter <-> Core communication layer
(TDD §3-4, §29). This is a Python stand-in for what the real VBA
`clsCoreClient` (adapters/coreldraw/src/CadIO/clsCoreClient.cls) does —
written so the communication contract (retry, idempotency, auth, error
mapping) is exercised by a real, automated end-to-end test now, since
actual CorelDRAW X7 isn't available in this environment to run and
verify VBA against (same limitation flagged for the VBA file itself).

Uses only `requests` + stdlib — no new heavy dependency, and this module
is a test/reference double, not a shipped production artifact, so it
isn't wired into pyproject's runtime dependency set.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

import requests

from core.exceptions import (
    AuthenticationException,
    GeometryFormatException,
    PersistenceException,
    PlatformException,
    PluginException,
    ResolutionException,
    SecurityException,
    ValidationException,
    WorkflowException,
)

# error_code -> exception class, mirroring core/api/errors.py's mapping
# in reverse. A real (non-Python) Adapter would instead switch on the
# stable error_code string directly; this reference client re-raises
# typed Python exceptions purely because it's convenient for testing
# Python-to-Python — see adapters/coreldraw/README.md for the caveat.
_ERROR_CODE_TO_EXCEPTION: dict[str, type[PlatformException]] = {
    "GEOMETRY_FORMAT_INVALID": GeometryFormatException,
    "AUTHENTICATION_FAILED": AuthenticationException,
    "VALIDATION": ValidationException,
}

_CATEGORY_TO_EXCEPTION: dict[str, type[PlatformException]] = {
    "validation": ValidationException,
    "security": SecurityException,
    "not_found": PersistenceException,
    "conflict": WorkflowException,
    "plugin_error": PluginException,
    "internal": ResolutionException,
}

RETRYABLE_STATUS_CODES = {502, 503, 504}


class CoreClientError(Exception):
    """Raised when the server returned a structured ErrorResponse that
    doesn't map to a known PlatformException subclass, or after retries
    are exhausted on a transient failure.
    """


@dataclass
class JobSubmissionResult:
    job_id: str
    status: str
    geometry: dict[str, Any]
    correlation_id: str


class CoreClient:
    """Localhost-only by construction (v3 §17.2) — base_url must point at
    127.0.0.1; this is enforced, not just conventional.
    """

    def __init__(
        self,
        auth_token: str,
        port: int,
        host: str = "127.0.0.1",
        max_retries: int = 3,
        backoff_seconds: float = 0.1,
        timeout_seconds: float = 5.0,
        session: requests.Session | None = None,
    ) -> None:
        if host != "127.0.0.1":
            raise ValueError("CoreClient only supports localhost (127.0.0.1) — v3 §17.2")
        self._base_url = f"http://{host}:{port}"
        self._auth_token = auth_token
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._timeout_seconds = timeout_seconds
        self._session = session or requests.Session()

    def health(self) -> dict:
        return self._request("GET", "/v1/health")

    def version(self) -> dict:
        return self._request("GET", "/v1/version")

    def submit_job(
        self,
        product_type: str,
        geometry: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> JobSubmissionResult:
        """idempotency_key defaults to a fresh uuid4 if not supplied —
        callers that want retry-safe resubmission across their *own*
        retries (e.g. after a network blip) should generate one key
        once and pass it to every attempt, which is exactly what the
        internal retry loop below does automatically.
        """
        key = idempotency_key or str(uuid.uuid4())
        body = self._request(
            "POST",
            "/v1/jobs",
            json_body={"product_type": product_type, "geometry": geometry},
            idempotency_key=key,
        )
        return JobSubmissionResult(
            job_id=body["job_id"],
            status=body["status"],
            geometry=body["geometry"],
            correlation_id=body["correlation_id"],
        )

    def _request(
        self,
        method: str,
        path: str,
        json_body: dict | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        headers = {
            "Authorization": f"Bearer {self._auth_token}",
            "X-Correlation-Id": str(uuid.uuid4()),
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                response = self._session.request(
                    method,
                    self._base_url + path,
                    json=json_body,
                    headers=headers,
                    timeout=self._timeout_seconds,
                )
            except requests.exceptions.RequestException as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    time.sleep(self._backoff_seconds * attempt)
                    continue
                raise CoreClientError(
                    f"{method} {path} failed after {self._max_retries} attempts: {exc}"
                ) from exc

            if response.status_code < 300:
                return response.json()

            if response.status_code in RETRYABLE_STATUS_CODES and attempt < self._max_retries:
                time.sleep(self._backoff_seconds * attempt)
                continue

            self._raise_for_error_response(response)

        # Unreachable in practice (loop always returns or raises), kept
        # for type-checker completeness.
        raise CoreClientError(f"{method} {path} failed: {last_exc}")

    def _raise_for_error_response(self, response: requests.Response) -> None:
        try:
            body = response.json()
        except ValueError:
            raise CoreClientError(
                f"HTTP {response.status_code} with non-JSON body: {response.text[:200]}"
            )

        error_code = body.get("error_code")
        category = body.get("category")
        message = body.get("message", "Core returned an error")
        context = {"details": body.get("details"), "correlation_id": body.get("correlation_id")}

        exc_class = _ERROR_CODE_TO_EXCEPTION.get(error_code) or _CATEGORY_TO_EXCEPTION.get(
            category
        )
        if exc_class is not None:
            raise exc_class(message, context=context)
        raise CoreClientError(f"{error_code}: {message} ({context})")
