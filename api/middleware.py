# api/middleware.py

from __future__ import annotations

import time
import uuid
import json
import logging
from typing import Callable

from flask import Flask, request, g
from werkzeug.wrappers import Response

# Create a dedicated logger
logger = logging.getLogger("api_requests")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def init_request_logging(app: Flask) -> None:
    """
    Installs before_request / after_request hooks to log all requests as JSON:

    Fields:
      - request_id     : uuid4 or X-Request-ID header
      - timestamp      : ISO 8601
      - method, path
      - status_code
      - latency_ms
      - client_ip
      - user_agent
      - error (if any)
    """

    @app.before_request
    def _before_request() -> None:
        # start timer
        g.start_time = time.time()

        # assign or propagate a request ID
        g.request_id = (
            request.headers.get("X-Request-ID")
            or str(uuid.uuid4())
        )

    @app.after_request
    def _after_request(response: Response) -> Response:
        _log_request(response.status_code)
        return response

    @app.teardown_request
    def _teardown_request(exc: Exception | None) -> None:
        if exc is not None:
            # an unhandled exception occurred
            # Flask will still call after_request with a 500, but we capture details here
            _log_request(
                status_code=getattr(g, "response_status", 500),
                error=str(exc)
            )

    def _log_request(status_code: int, error: str | None = None) -> None:
        latency_ms = int((time.time() - getattr(g, "start_time", time.time())) * 1000)
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
            "request_id": g.request_id,
            "method": request.method,
            "path": request.path,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "client_ip": request.remote_addr,
            "user_agent": request.user_agent.string,
        }
        if error:
            entry["error"] = error

        logger.info(json.dumps(entry))

        # store status in case teardown logs exceptions
        g.response_status = status_code

    # Optionally expose a decorator to wrap routes and propagate request_id
    def with_request_id(fn: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            # ensure the request_id is added to any response headers
            response = fn(*args, **kwargs)
            if isinstance(response, Response):
                response.headers["X-Request-ID"] = g.request_id
            return response
        wrapper.__name__ = fn.__name__
        return wrapper

    app.with_request_id = with_request_id
