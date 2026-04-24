import json
import hashlib
from typing import Any
from urllib.parse import quote

import httpx

from app.core.redis_keys import RedisKeys
import redis.asyncio as redis

from app.config.env_config import get_settings

try:
    from upstash_redis.asyncio import Redis as UpstashRedis
    from upstash_ratelimit.asyncio import Ratelimit, SlidingWindow
    HAS_UPSTASH_RATELIMIT = True
except ImportError:
    HAS_UPSTASH_RATELIMIT = False

class RedisCache:
    def __init__(self) -> None:
        settings = get_settings()
        self._mode = "redis"
        self._client: Any = None
        self._http_client: httpx.AsyncClient | None = None
        self._rest_url = settings.redis_rest_url.rstrip("/") if settings.redis_rest_url else ""
        self._rest_token = settings.redis_rest_token

        if self._rest_url and self._rest_token:
            self._mode = "rest"
            self._http_client = httpx.AsyncClient(
                timeout=10,
                headers={"Authorization": f"Bearer {self._rest_token}"},
            )
        else:
            self._client = redis.from_url(
                settings.redis_url,
                password=settings.redis_token or None,
                decode_responses=True,
            )
        self._default_ttl = settings.query_cache_ttl_seconds

        self._upstash_ratelimit = None
        if self._mode == "rest" and HAS_UPSTASH_RATELIMIT:
            upstash_redis_client = UpstashRedis(url=self._rest_url, token=self._rest_token)
            self._upstash_ratelimit = Ratelimit(
                redis=upstash_redis_client,
                limiter=SlidingWindow(max_requests=settings.max_pdf_uploads_per_hour, window=3600, unit="s"),
                prefix="@upstash/ratelimit"
            )

    async def _rest_get(self, key: str) -> dict[str, Any] | None:
        if not self._http_client or not self._rest_url:
            return None
        encoded_key = quote(key, safe="")
        response = await self._http_client.get(f"{self._rest_url}/get/{encoded_key}")
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result")
        if result is None:
            return None
        return json.loads(result)

    async def _rest_set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        if not self._http_client or not self._rest_url:
            return
        encoded_key = quote(key, safe="")
        encoded_value = quote(json.dumps(value), safe="")
        response = await self._http_client.post(
            f"{self._rest_url}/set/{encoded_key}/{encoded_value}",
            params={"EX": ttl_seconds},
        )
        response.raise_for_status()

    async def _rest_delete(self, key: str) -> None:
        if not self._http_client or not self._rest_url:
            return
        encoded_key = quote(key, safe="")
        response = await self._http_client.post(f"{self._rest_url}/del/{encoded_key}")
        response.raise_for_status()

    async def _rest_incr(self, key: str) -> int:
        if not self._http_client or not self._rest_url:
            return 1
        encoded_key = quote(key, safe="")
        response = await self._http_client.get(f"{self._rest_url}/incr/{encoded_key}")
        response.raise_for_status()
        payload = response.json()
        return int(payload.get("result", 1))

    async def _rest_expire(self, key: str, seconds: int) -> None:
        if not self._http_client or not self._rest_url:
            return
        encoded_key = quote(key, safe="")
        response = await self._http_client.get(f"{self._rest_url}/expire/{encoded_key}/{seconds}")
        response.raise_for_status()

    def _make_key(self, user_id: str, query: str, persona_id: str | None = None) -> str:
        key_scope = f"{user_id}:{query}:{persona_id or 'none'}"
        query_hash = hashlib.sha256(key_scope.encode()).hexdigest()[:16]
        return RedisKeys.query_cache(user_id, query_hash)

    async def get(self, key: str) -> dict[str, Any] | None:
        if self._mode == "rest":
            return await self._rest_get(key)

        if not self._client:
            return None
        value = await self._client.get(key)
        if value is None:
            return None
        return json.loads(value)

    async def set(self, key: str, value: dict[str, Any], ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds or self._default_ttl
        if self._mode == "rest":
            await self._rest_set(key, value, ttl)
            return

        if self._client:
            await self._client.setex(key, ttl, json.dumps(value))

    async def delete(self, key: str) -> None:
        if self._mode == "rest":
            await self._rest_delete(key)
            return

        if self._client:
            await self._client.delete(key)

    async def increment_rate_limit(self, key: str, limit: int, window_seconds: int) -> bool:
        """Returns True if the request is allowed, False if rate limited."""
        if self._upstash_ratelimit:
            # We use upstash_ratelimit which handles windowing internally based on its init configuration
            # The 'key' here acts as the identifier
            res = await self._upstash_ratelimit.limit(key)
            return res.allowed

        if self._mode == "rest":
            current = await self._rest_incr(key)
            if current == 1:
                await self._rest_expire(key, window_seconds)
            return current <= limit

        if not self._client:
            return True
            
        current = await self._client.incr(key)
        if current == 1:
            await self._client.expire(key, window_seconds)
        return current <= limit

    async def get_cached_query(self, user_id: str, query: str, persona_id: str | None = None) -> dict[str, Any] | None:
        key = self._make_key(user_id, query, persona_id)
        return await self.get(key)

    async def cache_query_result(
        self,
        user_id: str,
        query: str,
        persona_id: str | None,
        result: dict[str, Any],
        ttl_seconds: int | None = None,
    ) -> None:
        key = self._make_key(user_id, query, persona_id)
        await self.set(key, result, ttl_seconds)

    # ── Persona caching ──────────────────────────────────────────────

    async def get_cached_persona(self, persona_id: str) -> dict[str, Any] | None:
        """Return a single cached persona dict, or None on miss."""
        return await self.get(RedisKeys.persona(persona_id))

    async def cache_persona(self, persona_id: str, data: dict[str, Any]) -> None:
        """Cache a single persona."""
        await self.set(RedisKeys.persona(persona_id), data, RedisKeys.PERSONA_TTL_SECONDS)

    async def delete_cached_persona(self, persona_id: str) -> None:
        """Remove a single persona from cache."""
        await self.delete(RedisKeys.persona(persona_id))

    async def get_cached_persona_list(self, include_inactive: bool = False) -> list[dict[str, Any]] | None:
        """Return the cached persona list, or None on miss."""
        key = RedisKeys.PERSONA_LIST_ALL if include_inactive else RedisKeys.PERSONA_LIST_ACTIVE
        result = await self.get(key)
        return result  # already a list when present

    async def cache_persona_list(
        self, personas: list[dict[str, Any]], include_inactive: bool = False
    ) -> None:
        """Cache the full persona list."""
        key = RedisKeys.PERSONA_LIST_ALL if include_inactive else RedisKeys.PERSONA_LIST_ACTIVE
        await self.set(key, personas, RedisKeys.PERSONA_TTL_SECONDS)

    async def invalidate_all_personas(self) -> None:
        """Bust every persona-related cache entry (lists + individual)."""
        await self.delete(RedisKeys.PERSONA_LIST_ACTIVE)
        await self.delete(RedisKeys.PERSONA_LIST_ALL)

    # ── Document caching ──────────────────────────────────────────────
    async def get_cached_document(self, document_id: str) -> dict[str, Any] | None:
        return await self.get(RedisKeys.document(document_id))

    async def cache_document(self, document_id: str, data: dict[str, Any]) -> None:
        await self.set(RedisKeys.document(document_id), data, 3600)  # 1 hour

    async def delete_cached_document(self, document_id: str) -> None:
        await self.delete(RedisKeys.document(document_id))

    # ── Job status caching ──────────────────────────────────────────────
    async def get_cached_job_status(self, job_id: str) -> dict[str, Any] | None:
        return await self.get(RedisKeys.ingest_job(job_id))

    async def cache_job_status(self, job_id: str, data: dict[str, Any]) -> None:
        await self.set(RedisKeys.ingest_job(job_id), data, 60)  # 1 minute

    async def delete_cached_job_status(self, job_id: str) -> None:
        await self.delete(RedisKeys.ingest_job(job_id))

    # ── lifecycle ────────────────────────────────────────────────────

    async def close(self) -> None:
        if self._client:
            await self._client.close()
        if self._http_client:
            await self._http_client.aclose()


redis_cache = RedisCache()
