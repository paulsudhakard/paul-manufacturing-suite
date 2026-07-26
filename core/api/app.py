"""The Core HTTP API (TDD §4). Built on Python's stdlib WSGI machinery
rather than a third-party framework (FastAPI/Starlette etc.) — those
aren't installable in this environment (no network access to PyPI here),
and at Option A's single-shop, localhost-only scale a hand-rolled router
is entirely adequate. Route handlers are plain functions of
(ApiContext, Request) -> (status, body_dict), so swapping the transport
layer later doesn't require touching handler logic.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from core.api.errors import ErrorResponse, http_status_for
from core.api.idempotency import IdempotencyStore
from core.exceptions import AuthenticationException, PlatformException
from core.jobs import InMemoryJobStore
from core.logging import LogWriter

IDEMPOTENCY_HEADER = "HTTP_IDEMPOTENCY_KEY"
CORRELATION_HEADER = "HTTP_X_CORRELATION_ID"
AUTH_HEADER = "HTTP_AUTHORIZATION"


@dataclass
class ApiContext:
    """Everything a route handler might need — one object, passed
    explicitly, so handlers stay easy to unit test without a real server.
    """

    auth_token: str
    job_store: InMemoryJobStore
    idempotency_store: IdempotencyStore
    log_writer: LogWriter


@dataclass
class Request:
    method: str
    path: str
    correlation_id: str
    idempotency_key: str | None
    json_body: Any


Handler = Callable[[ApiContext, Request], tuple[int, dict]]


class Route:
    def __init__(self, method: str, pattern: str, handler: Handler) -> None:
        self.method = method
        self.regex = re.compile("^" + pattern + "$")
        self.handler = handler


class CoreApp:
    """WSGI application. Auth applies uniformly to every route (TDD §29
    — no endpoint is exempt, including /v1/health).
    """

    def __init__(self, context: ApiContext) -> None:
        self.context = context
        self.routes: list[Route] = []

    def add_route(self, method: str, pattern: str, handler: Handler) -> None:
        self.routes.append(Route(method, pattern, handler))

    def __call__(self, environ: dict, start_response: Callable) -> list[bytes]:
        method = environ["REQUEST_METHOD"]
        path = environ.get("PATH_INFO", "/")
        correlation_id = environ.get(CORRELATION_HEADER) or str(uuid.uuid4())
        idempotency_key = environ.get(IDEMPOTENCY_HEADER)

        status, body = self._dispatch(environ, method, path, correlation_id, idempotency_key)

        payload = json.dumps(body).encode("utf-8")
        headers = [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(payload))),
            ("X-Correlation-Id", correlation_id),
        ]
        start_response(_status_line(status), headers)
        return [payload]

    def _dispatch(
        self,
        environ: dict,
        method: str,
        path: str,
        correlation_id: str,
        idempotency_key: str | None,
    ) -> tuple[int, dict]:
        auth_error = self._check_auth(environ, correlation_id)
        if auth_error is not None:
            return auth_error

        if idempotency_key:
            cached = self.context.idempotency_store.get(idempotency_key)
            if cached is not None:
                return cached

        for route in self.routes:
            match = route.regex.match(path)
            if match and route.method == method:
                request = Request(
                    method=method,
                    path=path,
                    correlation_id=correlation_id,
                    idempotency_key=idempotency_key,
                    json_body=_read_json_body(environ),
                )
                status, body = self._invoke(route.handler, request)
                if idempotency_key and 200 <= status < 300:
                    self.context.idempotency_store.put(idempotency_key, status, body)
                return status, body
            if match:
                return 405, ErrorResponse(
                    correlation_id=correlation_id,
                    error_code="METHOD_NOT_ALLOWED",
                    category="validation",
                    message=f"{method} not allowed on {path}",
                ).to_dict()

        return 404, ErrorResponse(
            correlation_id=correlation_id,
            error_code="NOT_FOUND",
            category="not_found",
            message=f"No route for {method} {path}",
        ).to_dict()

    def _invoke(self, handler: Handler, request: Request) -> tuple[int, dict]:
        try:
            return handler(self.context, request)
        except PlatformException as exc:
            self.context.log_writer.log(
                "ERROR",
                exc.message,
                component="api",
                correlation_id=request.correlation_id,
                context={"error_code": http_status_for(exc), "category": exc.category},
            )
            return http_status_for(exc), ErrorResponse.from_exception(
                exc, request.correlation_id
            ).to_dict()
        except Exception as exc:  # unclassified — treated as a defect, TDD §18
            self.context.log_writer.log(
                "ERROR",
                f"Unclassified exception reached the API boundary: {exc!r}",
                component="api",
                correlation_id=request.correlation_id,
            )
            return 500, ErrorResponse.internal_error(request.correlation_id).to_dict()

    def _check_auth(self, environ: dict, correlation_id: str) -> tuple[int, dict] | None:
        from core.api.auth import extract_bearer_token

        token = extract_bearer_token(environ.get(AUTH_HEADER))
        if token != self.context.auth_token:
            exc = AuthenticationException("Missing or invalid bearer token")
            self.context.log_writer.log(
                "WARNING",
                exc.message,
                component="api.auth",
                correlation_id=correlation_id,
            )
            return 401, ErrorResponse.from_exception(exc, correlation_id).to_dict()
        return None


def _read_json_body(environ: dict) -> Any:
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    if length == 0:
        return None
    raw = environ["wsgi.input"].read(length)
    if not raw:
        return None
    return json.loads(raw)


def _status_line(status: int) -> str:
    reasons = {
        200: "OK",
        201: "Created",
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        409: "Conflict",
        500: "Internal Server Error",
        502: "Bad Gateway",
    }
    return f"{status} {reasons.get(status, 'Unknown')}"


def build_app(context: ApiContext) -> CoreApp:
    from core.api.v1.routes_geometry import validate_format
    from core.api.v1.routes_health import health
    from core.api.v1.routes_jobs import create_job
    from core.api.v1.routes_version import version

    app = CoreApp(context)
    app.add_route("GET", r"/v1/health", health)
    app.add_route("GET", r"/v1/version", version)
    app.add_route("POST", r"/v1/jobs", create_job)
    app.add_route("POST", r"/v1/geometry/validate-format", validate_format)
    return app
