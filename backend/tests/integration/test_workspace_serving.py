"""Exercise production page serving with the real Vite build (npm run build first)."""
import re
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

from app.clients.redis_cache import redis_cache
from app.main import app, web_dir


@pytest.mark.asyncio
async def test_built_workspace_and_assets_share_the_api_origin(monkeypatch):
    expected = Path(__file__).resolve().parents[3] / 'frontend' / 'dist'
    assert web_dir == expected
    assert (web_dir / 'index.html').is_file(), 'Run npm run build in frontend first'
    monkeypatch.setattr(redis_cache, 'increment_rate_limit', AsyncMock(return_value=True))
    monkeypatch.setattr(redis_cache, 'get_raw', AsyncMock(return_value='1'))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        for path in ['/login', '/signup', '/workspace', '/profile', '/forgot-password', '/reset-password']:
            response = await client.get(path)
            assert response.status_code == 200
            assert 'text/html' in response.headers['content-type']
            assert response.headers['cache-control'] == 'no-store'
            assets = re.findall(r'(?:src|href)="(/assets/[^"]+)"', response.text)
            assert assets
            for asset in assets:
                assert (await client.get(asset)).status_code == 200
        response = await client.get('/api/v1/auth/me')
        assert response.status_code == 401
        assert response.json()['detail'] == 'Sign in to continue'
        for path in ['/api/v1/rag/sessions', '/api/v1/rag/sessions/example/documents', '/api/v1/rag/sessions/example/history']:
            assert (await client.get(path)).status_code == 401
