"""Centralized logging configuration for the RAG service.

Logs are always written to stdout so container/systemd collectors can capture
them. Set ``LOG_TO_FILE=true`` (the default) to also persist them to a rotating
file under ``LOG_DIR``. ``LOG_FORMAT=json`` emits one JSON object per line for
log aggregators, while the default ``text`` format stays human readable.

Every request gets a sanitized request ID from ``X-Request-ID`` (or a generated
one). A context variable carries it to every log line emitted while the request
is handled, and the JSON formatter exposes it as ``request_id``.
"""

import json
import logging
import logging.handlers
import re
import sys
import uuid
from contextlib import suppress
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config.env_config import get_settings

BASE_DIR = Path(__file__).resolve().parents[2]
_REQUEST_ID_MAX_LENGTH = 64
_UNSAFE_REQUEST_ID_CHARS = re.compile(r"[^A-Za-z0-9._-]")

request_id_var: ContextVar[str] = ContextVar("rag_request_id", default="-")
_configured = False
_installed_handlers: list[logging.Handler] = []


def normalize_request_id(value: str | None) -> str | None:
    """Strip unsafe characters so request IDs cannot forge log lines."""
    if not value:
        return None
    cleaned = _UNSAFE_REQUEST_ID_CHARS.sub("", value.strip())[:_REQUEST_ID_MAX_LENGTH]
    return cleaned or None


def set_request_id(value: str | None = None) -> Token[str]:
    """Bind a request ID to the current async context."""
    return request_id_var.set(normalize_request_id(value) or uuid.uuid4().hex)


def reset_request_id(token: Token[str]) -> None:
    request_id_var.reset(token)


def get_request_id() -> str:
    return request_id_var.get()


class RequestIdFilter(logging.Filter):
    """Attach the active request ID to every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = request_id_var.get()
        return True


def _timestamp(record: logging.LogRecord) -> str:
    return (
        datetime.fromtimestamp(record.created, tz=UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


class JsonFormatter(logging.Formatter):
    """One JSON object per line, suitable for Loki/CloudWatch/Datadog."""

    extra_fields = ("method", "path", "status_code", "duration_ms", "client_ip", "user_agent")

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": _timestamp(record),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", request_id_var.get()),
            "message": record.getMessage(),
        }
        for field in self.extra_fields:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """Compact, aligned, UTC text output for local development."""

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s | %(levelname)-8s | %(request_id)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )

    def formatTime(  # noqa: N802 - required camelCase override of logging.Formatter
        self, record: logging.LogRecord, datefmt: str | None = None
    ) -> str:
        return datetime.fromtimestamp(record.created, tz=UTC).strftime(
            datefmt or "%Y-%m-%dT%H:%M:%SZ"
        )


def get_logger(name: str) -> logging.Logger:
    """Return a logger inside the shared ``rag`` namespace."""
    if name == "rag" or name.startswith("rag."):
        return logging.getLogger(name)
    return logging.getLogger(f"rag.{name}")


def _parse_level(value: str) -> int:
    level = getattr(logging, str(value).strip().upper(), None)
    return level if isinstance(level, int) else logging.INFO


def _resolve_log_file(log_dir: str, filename: str) -> Path:
    directory = Path(log_dir)
    if not directory.is_absolute():
        directory = BASE_DIR / directory
    return directory / Path(filename).name


def _prepare(handler: logging.Handler, formatter: logging.Formatter) -> logging.Handler:
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())
    return handler


def configure_logging(force: bool = False) -> None:
    """Configure root logging once. Safe to call multiple times."""
    global _configured
    if _configured and not force:
        return

    settings = get_settings()
    level = _parse_level(settings.log_level)
    formatter: logging.Formatter = (
        JsonFormatter() if settings.log_format == "json" else TextFormatter()
    )

    handlers: list[logging.Handler] = [
        _prepare(logging.StreamHandler(sys.stdout), formatter)
    ]

    file_error: OSError | None = None
    if settings.log_to_file:
        try:
            log_file = _resolve_log_file(settings.log_dir, settings.log_filename)
            log_file.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(
                _prepare(
                    logging.handlers.RotatingFileHandler(
                        log_file,
                        maxBytes=settings.log_max_bytes,
                        backupCount=settings.log_backup_count,
                        encoding="utf-8",
                    ),
                    formatter,
                )
            )
        except OSError as exc:
            file_error = exc

    root = logging.getLogger()
    for handler in list(_installed_handlers):
        root.removeHandler(handler)
        with suppress(Exception):
            handler.close()
    _installed_handlers.clear()

    for handler in handlers:
        root.addHandler(handler)
        _installed_handlers.append(handler)
    root.setLevel(level)

    # Send uvicorn startup/error logs through the same formatter and file.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.asgi"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
        uvicorn_logger.setLevel(level)

    # RequestLoggingMiddleware writes richer access logs, so silence the
    # duplicate uvicorn access line.
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers.clear()
    access_logger.propagate = False
    access_logger.setLevel(logging.WARNING)

    # Dependency chatter stays quiet unless it is actionable.
    for name in ("httpx", "httpcore", "urllib3", "sqlalchemy.engine"):
        logging.getLogger(name).setLevel(logging.WARNING)

    logging.captureWarnings(True)
    _configured = True

    if file_error is not None:
        get_logger("logging").warning("File logging disabled: %s", file_error)


logger = get_logger("rag")
