"""Starts the Core HTTP API. Bound strictly to 127.0.0.1 — never 0.0.0.0
(v3 §17.2) — enforced here with a hard assertion, not just a config
default, per Sprint 2's original acceptance criterion.

Run with:  python3 -m core.api.server
"""

from __future__ import annotations

import sys
from wsgiref.simple_server import WSGIRequestHandler, make_server

from core.api.app import ApiContext, build_app
from core.api.auth import AuthTokenManager
from core.api.idempotency import IdempotencyStore
from core.config import ConfigLoader, CoreConfig
from core.jobs import InMemoryJobStore
from core.logging import LogWriter


class _QuietHandler(WSGIRequestHandler):
    """Suppress wsgiref's default per-request stderr logging — Core's own
    structured LogWriter is the single source of truth for request logs.
    """

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        pass


class ThreadingWSGIServer:
    """Thin wrapper so callers don't need to know wsgiref's API shape."""

    def __init__(self, host: str, port: int, app) -> None:
        import socketserver
        from wsgiref.simple_server import WSGIServer

        class _ThreadingWSGIServer(socketserver.ThreadingMixIn, WSGIServer):
            daemon_threads = True

        self._httpd = make_server(
            host, port, app, server_class=_ThreadingWSGIServer, handler_class=_QuietHandler
        )

    @property
    def port(self) -> int:
        return self._httpd.server_port

    def serve_forever(self) -> None:
        self._httpd.serve_forever()

    def shutdown(self) -> None:
        self._httpd.shutdown()

    def server_close(self) -> None:
        self._httpd.server_close()


def build_server(config: CoreConfig, log_writer: LogWriter) -> tuple[ThreadingWSGIServer, str]:
    assert config.api.bind_host == "127.0.0.1", (
        f"Refusing to bind to {config.api.bind_host!r} — Core must bind to 127.0.0.1 only "
        "(v3 §17.2). This is a hard startup assertion, not just a config default."
    )

    token = AuthTokenManager(config.api.auth_token_path).generate_and_persist()
    context = ApiContext(
        auth_token=token,
        job_store=InMemoryJobStore(),
        idempotency_store=IdempotencyStore(),
        log_writer=log_writer,
    )
    app = build_app(context)
    server = ThreadingWSGIServer(config.api.bind_host, config.api.port, app)
    return server, token


def main() -> int:
    config: CoreConfig = ConfigLoader.load(config_path="config.yaml")
    log_writer = LogWriter(
        log_dir=config.logging.log_dir,
        retention_days=config.logging.retention_days,
    )

    try:
        server, _token = build_server(config, log_writer)

        print("PMS Core API starting...")
        print(f"Listening on http://{config.api.bind_host}:{server.port}")
        print(f"Auth token written to: {config.api.auth_token_path}")

        log_writer.log(
            "INFO",
            "PMS Core API starting",
            component="api.server",
            context={"bind_host": config.api.bind_host, "port": server.port},
        )

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down (Ctrl+C received)...")
        finally:
            server.shutdown()
            server.server_close()
            log_writer.log("INFO", "PMS Core API shut down cleanly", component="api.server")

        return 0
    finally:
        log_writer.close()


if __name__ == "__main__":
    sys.exit(main())
