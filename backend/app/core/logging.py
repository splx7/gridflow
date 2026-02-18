"""Structured JSON logging and request ID middleware."""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter with request ID injection."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        log_entry: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        rid = request_id_var.get("")
        if rid:
            log_entry["request_id"] = rid

        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Include extra fields
        for key in ("method", "path", "status_code", "duration_ms", "client_ip"):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        return json.dumps(log_entry)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that adds X-Request-ID header and logs request timing."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        rid = request.headers.get("x-request-id", str(uuid.uuid4())[:8])
        request_id_var.set(rid)

        start = time.perf_counter()
        response: Response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)

        response.headers["X-Request-ID"] = rid

        logger = logging.getLogger("gridflow.access")
        logger.info(
            "%s %s → %s (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={
                "method": request.method,
                "path": str(request.url.path),
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": request.client.host if request.client else "unknown",
            },
        )

        return response


def setup_logging(json_format: bool = False) -> None:
    """Configure root logger. Use json_format=True for production."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    # Remove existing handlers to avoid duplicates
    root.handlers.clear()
    root.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
