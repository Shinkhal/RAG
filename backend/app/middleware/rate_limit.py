
from typing import Optional

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.clients.redis_cache import redis_cache
from app.config.env_config import get_settings
from app.utils.logger import get_logger

logger = get_logger("rate_limit")


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, exclude_paths: Optional[list[str]] = None):
        super().__init__(app)
        self._exclude = set(exclude_paths or [])

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self._exclude or request.url.path.startswith("/assets/"):
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        settings = get_settings()

        if request.url.path in {"/api/v1/auth/login", "/api/v1/auth/signup"}:
            limit, window = 10, 60
            key = f"rate_limit:auth:{ip}"
        else:
            limit = settings.rate_limit_tier_max["free"]
            window = settings.rate_limit_window_seconds
            key = f"rate_limit:{ip}"
        allowed = await redis_cache.increment_rate_limit(key, limit, window)
        if not allowed:
            logger.warning(
                "Rate limit exceeded: %s %s",
                request.method,
                request.url.path,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "client_ip": ip,
                },
            )
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded ({limit} req/{window}s)"},
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(window),
                },
            )

        raw_value = await redis_cache.get_raw(key)
        count = int(raw_value) if raw_value else 1
        remaining = max(limit - count, 0)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
