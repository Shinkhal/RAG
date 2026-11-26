import asyncio
import threading

import cloudinary.api
import pytest

from app.config.cloudinary_config import CloudinaryConfig


@pytest.mark.asyncio
async def test_health_check_runs_off_event_loop_with_timeout(monkeypatch):
    main_thread = threading.get_ident()

    def ping(**options):
        assert threading.get_ident() != main_thread
        assert options['timeout'] == 5
        return {'status': 'ok'}

    monkeypatch.setattr(CloudinaryConfig, '_initialized', True)
    monkeypatch.setattr(cloudinary.api, 'ping', ping)
    assert await CloudinaryConfig.health_check() is True


@pytest.mark.asyncio
async def test_unavailable_storage_reports_unhealthy(monkeypatch):
    def ping(**options):
        raise TimeoutError('storage unavailable')

    monkeypatch.setattr(CloudinaryConfig, '_initialized', True)
    monkeypatch.setattr(cloudinary.api, 'ping', ping)
    assert await CloudinaryConfig.health_check() is False


@pytest.mark.asyncio
async def test_health_check_has_overall_deadline(monkeypatch):
    async def wait_for(awaitable, timeout):
        assert timeout == 6
        awaitable.close()
        raise asyncio.TimeoutError

    monkeypatch.setattr(CloudinaryConfig, '_initialized', True)
    monkeypatch.setattr(asyncio, 'wait_for', wait_for)
    assert await CloudinaryConfig.health_check() is False
