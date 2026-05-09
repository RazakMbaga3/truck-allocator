"""
app/logging_config.py — Structured JSON logging for the Smart Return Truck Allocator.

Provides:
  - JSON log format for production (one JSON object per line, easy to ingest into
    log aggregators like Grafana Loki, CloudWatch, Datadog)
  - Human-readable colored format for development (rich.logging.RichHandler)
  - Context fields: request_id, user_ip, path, method auto-injected via middleware
  - Log levels driven by APP_LOG_LEVEL env var (default: INFO)

Usage:
    from app.logging_config import configure_logging
    configure_logging()          # call once in main.py or lifespan

    import logging
    logger = logging.getLogger(__name__)
    logger.info("matching_complete", extra={"schedule_id": 42, "proposals": 3})

JSON output example (production):
    {
      "ts": "2026-04-27T10:30:00.123Z",
      "level": "INFO",
      "logger": "app.services.matching_engine",
      "msg": "matching_complete",
      "schedule_id": 42,
      "proposals": 3,
      "request_id": "req-abc123",
      "pid": 1234
    }
"""

from __future__ import annotations

import json
import logging
import logging.config
import os
import sys
import time
import uuid
from typing import Any

# ── Context storage (per-request injection) ───────────────────────────────────
# Using a simple dict here instead of contextvars for broad compatibility.
# FastAPI middleware populates this; log formatter reads it.

_request_context: dict[str, str] = {}


def set_request_context(request_id: str, method: str = "", path: str = "", ip: str = "") -> None:
    """Called by RequestLoggingMiddleware at the start of each request."""
    _request_context.clear()
    _request_context.update(
        request_id=request_id,
        method=method,
        path=path,
        ip=ip,
    )


def clear_request_context() -> None:
    _request_context.clear()


# ── JSON Formatter ─────────────────────────────────────────────────────────────

class JSONLogFormatter(logging.Formatter):
    """
    Emit log records as single-line JSON objects.

    Standard fields: ts, level, logger, msg, pid
    Request context fields: request_id, method, path, ip (if set)
    Extra fields: any kwargs passed as extra={} to logger calls
    """

    RESERVED = frozenset({
        "args", "asctime", "created", "exc_info", "exc_text", "filename",
        "funcName", "levelname", "levelno", "lineno", "message", "module",
        "msecs", "msg", "name", "pathname", "process", "processName",
        "relativeCreated", "stack_info", "taskName", "thread", "threadName",
    })

    def format(self, record: logging.LogRecord) -> str:
        # Build base record
        doc: dict[str, Any] = {
            "ts":     self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S") + "Z",
            "level":  record.levelname,
            "logger": record.name,
            "msg":    record.getMessage(),
            "pid":    record.process,
        }

        # Inject request context if present
        if _request_context:
            doc.update(_request_context)

        # Inject any extra={} fields the caller provided
        for key, value in record.__dict__.items():
            if key not in self.RESERVED and not key.startswith("_"):
                try:
                    json.dumps(value)  # only include JSON-serialisable values
                    doc[key] = value
                except (TypeError, ValueError):
                    doc[key] = str(value)

        # Include exception if present
        if record.exc_info:
            doc["exc"] = self.formatException(record.exc_info)

        return json.dumps(doc, ensure_ascii=False)


# ── Request Logging Middleware ─────────────────────────────────────────────────

class RequestLoggingMiddleware:
    """
    ASGI middleware that:
    1. Assigns a unique request_id to every HTTP request
    2. Injects context into the log record (via set_request_context)
    3. Logs request start and end (method, path, status, duration_ms)

    Skips: /api/schedules/feed (SSE — long-lived connection would spam logs)
           /static/* (static assets)
    """

    _SKIP_PREFIXES = ("/static/", "/api/schedules/feed")

    def __init__(self, app):
        self.app = app
        self._logger = logging.getLogger("app.http")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        if any(path.startswith(pfx) for pfx in self._SKIP_PREFIXES):
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        client = scope.get("client")
        ip = client[0] if client else "unknown"
        request_id = str(uuid.uuid4())[:8]

        set_request_context(request_id=request_id, method=method, path=path, ip=ip)

        t0 = time.perf_counter()
        status_code = 0

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 0)
            await send(message)

        try:
            self._logger.info(
                "request_start",
                extra={"request_id": request_id, "method": method, "path": path, "ip": ip},
            )
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = round((time.perf_counter() - t0) * 1000, 1)
            level = logging.WARNING if status_code >= 400 else logging.INFO
            self._logger.log(
                level,
                "request_end",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status": status_code,
                    "duration_ms": duration_ms,
                    "ip": ip,
                },
            )
            clear_request_context()


# ── Configure logging ──────────────────────────────────────────────────────────

def configure_logging(log_level: str | None = None) -> None:
    """
    Configure the root logger.

    In production (LOG_FORMAT=json or when stdout is not a tty):
        → JSON formatter on stdout
    In development (tty / LOG_FORMAT=human):
        → Rich handler with colors

    Call this ONCE at application startup (e.g., in main.py lifespan or
    uvicorn pre-startup hook).
    """
    level_name = (
        log_level
        or os.environ.get("APP_LOG_LEVEL", "INFO")
    ).upper()
    level = getattr(logging, level_name, logging.INFO)

    # Determine format: explicit env var wins; otherwise detect tty
    log_format = os.environ.get("LOG_FORMAT", "").lower()
    use_json = log_format == "json" or (log_format != "human" and not sys.stdout.isatty())

    if use_json:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONLogFormatter())
    else:
        try:
            from rich.logging import RichHandler
            handler = RichHandler(
                rich_tracebacks=True,
                show_time=True,
                show_path=True,
                markup=True,
            )
        except ImportError:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(
                logging.Formatter(
                    fmt="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
                    datefmt="%H:%M:%S",
                )
            )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicate output
    for existing in root_logger.handlers[:]:
        root_logger.removeHandler(existing)

    root_logger.addHandler(handler)

    # Silence noisy third-party loggers
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "apscheduler.executors"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Keep uvicorn error-level logs
    logging.getLogger("uvicorn.error").setLevel(logging.ERROR)

    logger = logging.getLogger(__name__)
    logger.info(
        "logging_configured",
        extra={"level": level_name, "format": "json" if use_json else "human"},
    )
