"""Tests for centralized logging, request correlation, and file persistence."""

import json
import logging
import sys
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from app.core.middleware import RequestLoggingMiddleware
from app.utils import logger as logger_module
from app.utils.logger import (
    JsonFormatter,
    RequestIdFilter,
    TextFormatter,
    configure_logging,
    get_logger,
    get_request_id,
    normalize_request_id,
    reset_request_id,
    set_request_id,
)

_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.asgi", "uvicorn.access")


@pytest.fixture
def isolated_logging(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Preserve and restore root/uvicorn handlers around configure_logging."""
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    uvicorn_state = {
        name: (list(logging.getLogger(name).handlers), logging.getLogger(name).propagate, logging.getLogger(name).level)
        for name in _UVICORN_LOGGERS
    }
    original_installed = list(logger_module._installed_handlers)
    original_configured = logger_module._configured

    logger_module._installed_handlers = []
    logger_module._configured = False

    yield

    for handler in list(logger_module._installed_handlers):
        root.removeHandler(handler)
        handler.close()
    logger_module._installed_handlers = original_installed
    logger_module._configured = original_configured

    for handler in list(root.handlers):
        root.removeHandler(handler)
    for handler in original_handlers:
        root.addHandler(handler)
    root.setLevel(original_level)

    for name, (handlers, propagate, level) in uvicorn_state.items():
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = handlers
        uvicorn_logger.propagate = propagate
        uvicorn_logger.setLevel(level)


def _record(message: str = "hello %s", args: tuple[Any, ...] = ("world",)) -> logging.LogRecord:
    return logging.LogRecord(
        name="rag.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg=message,
        args=args,
        exc_info=None,
    )


def test_normalize_request_id_removes_unsafe_characters() -> None:
    assert normalize_request_id("  abc-123.def_ghi  ") == "abc-123.def_ghi"
    assert normalize_request_id("bad id\nwith spaces") == "badidwithspaces"
    assert normalize_request_id("x" * 200) == "x" * 64
    assert normalize_request_id("") is None
    assert normalize_request_id(None) is None
    assert normalize_request_id("!!!") is None


def test_request_id_filter_reads_context() -> None:
    token = set_request_id("request-42")
    try:
        record = _record()
        assert RequestIdFilter().filter(record) is True
        assert record.request_id == "request-42"
    finally:
        reset_request_id(token)


def test_json_formatter_emits_structured_fields() -> None:
    record = _record()
    record.request_id = "request-42"
    record.method = "GET"
    record.path = "/api/v1/rag/query"
    record.status_code = 200
    record.duration_ms = 12.5
    record.client_ip = "127.0.0.1"
    record.user_agent = "test-client/1.0"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "rag.test"
    assert payload["request_id"] == "request-42"
    assert payload["message"] == "hello world"
    assert payload["method"] == "GET"
    assert payload["path"] == "/api/v1/rag/query"
    assert payload["status_code"] == 200
    assert payload["duration_ms"] == 12.5
    assert payload["client_ip"] == "127.0.0.1"
    assert payload["user_agent"] == "test-client/1.0"
    assert payload["timestamp"].endswith("Z")


def test_json_formatter_includes_exceptions() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        exc_info = sys.exc_info()

    record = logging.LogRecord("rag.test", logging.ERROR, __file__, 12, "failed", None, exc_info)
    payload = json.loads(JsonFormatter().format(record))

    assert "ValueError: boom" in payload["exception"]


def test_text_formatter_is_compact_and_includes_request_id() -> None:
    record = _record()
    record.request_id = "request-42"

    output = TextFormatter().format(record)

    assert " | INFO     | request-42 | rag.test | hello world" in output
    assert output.endswith("Z | INFO     | request-42 | rag.test | hello world")


def test_configure_logging_writes_json_to_rotating_file(
    tmp_path, monkeypatch: pytest.MonkeyPatch, isolated_logging: None
) -> None:
    monkeypatch.setenv("LOG_TO_FILE", "true")
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_FILENAME", "test.log")
    monkeypatch.setenv("LOG_FORMAT", "json")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")

    configure_logging(force=True)
    get_logger("test").info("persisted", extra={"path": "/api/v1/health", "status_code": 200})

    for handler in logger_module._installed_handlers:
        handler.flush()

    lines = (tmp_path / "test.log").read_text(encoding="utf-8").strip().splitlines()
    payload = json.loads(lines[-1])
    assert payload["message"] == "persisted"
    assert payload["path"] == "/api/v1/health"
    assert payload["status_code"] == 200
    assert payload["request_id"] == "-"
    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_is_idempotent(isolated_logging: None) -> None:
    configure_logging(force=True)
    handlers = list(logging.getLogger().handlers)

    configure_logging()

    assert list(logging.getLogger().handlers) == handlers


@pytest.mark.asyncio
async def test_request_middleware_sets_ids_logs_and_skips_health(caplog: pytest.LogCaptureFixture) -> None:
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/api/v1/ping")
    async def ping() -> dict[str, str]:
        return {"request_id": get_request_id()}

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    transport = httpx.ASGITransport(app=app)
    with caplog.at_level(logging.INFO, logger="rag.request"):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/ping",
                headers={"X-Request-ID": "abc 123!", "User-Agent": "test-client/1.0"},
            )
            health_response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["request_id"] == "abc123"
    assert response.headers["X-Request-ID"] == "abc123"
    assert response.headers["X-Process-Time"].endswith("ms")
    assert response.headers["Cache-Control"] == "no-store"

    messages = [record.message for record in caplog.records if record.name == "rag.request"]
    assert any("GET /api/v1/ping -> 200" in message for message in messages)
    assert not any("/health" in message for message in messages)
    access = next(record for record in caplog.records if record.name == "rag.request")
    assert access.user_agent == "test-client/1.0"
    assert access.client_ip == "127.0.0.1"

    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_request_middleware_generates_request_id() -> None:
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"request_id": get_request_id()}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ping")

    request_id = response.json()["request_id"]
    assert len(request_id) == 32
    assert response.headers["X-Request-ID"] == request_id
