import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.utils.logger import (
    get_logger,
    get_request_id,
    reset_request_id,
    set_request_id,
)

logger = get_logger("request")

_SKIP_ACCESS_PATHS = {"/health", "/favicon.ico"}
_SKIP_ACCESS_PREFIXES = ("/assets/",)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Attach a request ID and emit one structured access log per request."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        token = set_request_id(request.headers.get("X-Request-ID"))
        request_id = get_request_id()
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.exception(
                "%s %s failed after %.2fms",
                method,
                path,
                duration_ms,
                extra={
                    "method": method,
                    "path": path,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip,
                    "user_agent": user_agent,
                },
            )
            raise
        else:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            if self._should_log(method, path):
                logger.info(
                    "%s %s -> %s in %.2fms",
                    method,
                    path,
                    response.status_code,
                    duration_ms,
                    extra={
                        "method": method,
                        "path": path,
                        "status_code": response.status_code,
                        "duration_ms": duration_ms,
                        "client_ip": client_ip,
                        "user_agent": user_agent,
                    },
                )

            response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"
            response.headers["X-Request-ID"] = request_id
            if path.startswith("/api/"):
                response.headers["Cache-Control"] = "no-store"
            return response
        finally:
            reset_request_id(token)

    @staticmethod
    def _should_log(method: str, path: str) -> bool:
        if method == "OPTIONS":
            return False
        if path in _SKIP_ACCESS_PATHS:
            return False
        return not path.startswith(_SKIP_ACCESS_PREFIXES)
