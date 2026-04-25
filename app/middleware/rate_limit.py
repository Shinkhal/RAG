
from typing import Optional

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.clients.redis_cache import redis_cache
from app.config.env_config import get_settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, exclude_paths: Optional[list[str]] = None):
        super().__init__(app)
        self._exclude = set(exclude_paths or [])

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self._exclude:
            return await call_next(request)

        ip = request.client.host or "unknown"
        settings = get_settings()

        # Use tier-based limits from security config
        tier = self._extract_tier(request)
        limit = settings.rate_limit_tier_max.get(tier, 100)
        window = settings.rate_limit_window_seconds

        key = f"rate_limit:{ip}"
        allowed = await redis_cache.increment_rate_limit(key, limit, window)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded ({limit} req/{window}s for {tier} tier)"},
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

    def _extract_tier(self, request: Request) -> str:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
            if token.startswith("ent_"):
                return "enterprise"
            if token.startswith("pro_"):
                return "pro"
        return "free"
