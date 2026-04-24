
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config.redis_config import RedisConnection


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = request.client.host or "unknown"
        key = f"rate_limit:{ip}"
        limit = 100
        window = 60  # seconds
        redis = RedisConnection.get_instance()
        raw = redis.get(key)
        if raw is None:
            redis.set(key, "1")
            count = 1
        else:
            try:
                count = int(raw.get("data", raw)) if isinstance(raw, dict) else int(raw)
            except Exception:
                count = 0
        if count >= limit:
            return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
        remaining = limit - count
        redis.incr(key)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))
        return response
