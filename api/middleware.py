"""Request logging middleware for Flask apps.

Usage:
    from flask import Flask
    from api.middleware import init_request_logging

    app = Flask(__name__)
    init_request_logging(app)  # installs hooks & exposes app.with_request_id
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from functools import wraps
from typing import Callable, Set

from flask import Flask, g, request
from werkzeug.wrappers import Response

__all__ = ["init_request_logging"]

# ────────────────────────────────────────────────
# Logger setup
# ────────────────────────────────────────────────

def _create_logger() -> logging.Logger:  # pragma: no cover
    """Create (or reuse) a logger that emits one-line JSON entries."""
    logger = logging.getLogger("api_requests")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        # Prevent double-logging via root logger
        logger.propagate = False
    logger.setLevel(logging.INFO)
    return logger


logger = _create_logger()

# ────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────

def init_request_logging(
    app: Flask,
    *,
    skip_paths: Set[str] | None = None,
    request_id_header: str = "X-Request-ID",
) -> None:
    """Attach before/after/teardown hooks to *app* to JSON-log every request.

    Parameters
    ----------
    app:
        The Flask application instance to instrument.
    skip_paths:
        Optional set of URL paths that should *not* be logged
        (e.g. health-check endpoints, static assets).
    request_id_header:
        HTTP header used to propagate a caller-supplied request ID.
    """

    skip_paths = skip_paths or set()

    # ── before_request ──────────────────────────
    @app.before_request  # type: ignore[misc]
    def _before_request() -> None:  # pragma: no cover
        # High-resolution monotonic start time
        g.start_time = time.perf_counter()

        # Propagate or generate a request-correlation UUID
        g.request_id = (
            request.headers.get(request_id_header) or str(uuid.uuid4())
        )

    # ── after_request ───────────────────────────
    @app.after_request  # type: ignore[misc]
    def _after_request(response: Response) -> Response:  # pragma: no cover
        # Store status for teardown (in case of unhandled errors later)
        g.response_status = response.status_code
        _log_request(response.status_code)
        # Expose request ID back to caller
        response.headers[request_id_header] = g.request_id
        return response

    # ── teardown_request ────────────────────────
    @app.teardown_request  # type: ignore[misc]
    def _teardown_request(exc: Exception | None) -> None:  # pragma: no cover
        if exc is not None:
            # An unhandled exception occurred; log with error details.
            _log_request(
                status_code=getattr(g, "response_status", 500),
                error=str(exc),
            )

    # ── internal helper ─────────────────────────
    def _log_request(status_code: int, error: str | None = None) -> None:
        if request.path in skip_paths:
            return  # silence noisy or irrelevant endpoints

        latency_ms = int((time.perf_counter() - g.start_time) * 1000)
        client_ip = (
            request.headers.get("X-Forwarded-For", request.remote_addr or "-")
            .split(",")[0]
            .strip()
        )

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": g.request_id,
            "method": request.method,
            "path": request.path,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "client_ip": client_ip,
            "user_agent": request.user_agent.string,
        }
        if error:
            entry["error"] = error

        logger.info(json.dumps(entry, separators=(",", ":"), ensure_ascii=False))

    # ── helper decorator for routes ─────────────
    def with_request_id(fn: Callable) -> Callable:  # type: ignore[override]
        """Decorator that injects *request_id_header* in route responses."""

        @wraps(fn)
        def wrapper(*args, **kwargs):  # type: ignore[override]
            resp = fn(*args, **kwargs)
            if isinstance(resp, Response):
                resp.headers.setdefault(request_id_header, g.request_id)
            return resp

        return wrapper

    # Attach helper to the app instance for convenience
    app.with_request_id = with_request_id  # type: ignore[attr-defined]
