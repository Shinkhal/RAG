"""Unit tests for the Redis REST transport helpers."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.clients.redis_cache import RedisCache


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeHTTPClient:
    def __init__(self) -> None:
        self.posts: list[dict[str, Any]] = []
        self.gets: list[str] = []
        self.get_payload: dict[str, Any] = {"result": None}

    async def post(self, url: str, *, json: Any = None, params: Any = None) -> FakeResponse:
        self.posts.append({"url": url, "json": json, "params": params})
        return FakeResponse({"result": "OK"})

    async def get(self, url: str) -> FakeResponse:
        self.gets.append(url)
        return FakeResponse(self.get_payload)


def _rest_cache(http_client: FakeHTTPClient) -> RedisCache:
    cache = RedisCache.__new__(RedisCache)
    cache._mode = "rest"
    cache._rest_url = "https://redis.example"
    cache._rest_token = "token"
    cache._http_client = http_client  # type: ignore[assignment]
    cache._client = None
    cache._default_ttl = 60
    return cache


@pytest.mark.asyncio
async def test_rest_set_sends_value_in_request_body() -> None:
    http_client = FakeHTTPClient()
    cache = _rest_cache(http_client)
    value = {"full_text": "x" * 200_000}

    await cache.set("doc_context:doc-1", value, 86400)

    assert len(http_client.posts) == 1
    request = http_client.posts[0]
    # The value must not be placed in the URL path: large document contexts
    # exceed httpx's URL limit.
    assert request["url"] == "https://redis.example"
    assert request["json"][0] == "SET"
    assert request["json"][1] == "doc_context:doc-1"
    assert json.loads(request["json"][2]) == value
    assert request["json"][3:] == ["EX", 86400]


@pytest.mark.asyncio
async def test_rest_get_parses_json_string_values() -> None:
    http_client = FakeHTTPClient()
    http_client.get_payload = {"result": json.dumps({"hello": "world"})}
    cache = _rest_cache(http_client)

    assert await cache.get("doc_context:doc-1") == {"hello": "world"}


@pytest.mark.asyncio
async def test_rest_get_returns_already_decoded_values() -> None:
    http_client = FakeHTTPClient()
    http_client.get_payload = {"result": {"hello": "world"}}
    cache = _rest_cache(http_client)

    assert await cache.get("doc_context:doc-1") == {"hello": "world"}
