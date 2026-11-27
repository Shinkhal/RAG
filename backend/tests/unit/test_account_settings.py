"""Tests for profile and password management endpoints."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from app.api.auth import (
    PasswordChangeRequest,
    ProfileUpdateRequest,
    _hash_password,
    _verify_password,
    change_password,
    update_profile,
)
from app.db.models import Account


def _account() -> Account:
    return Account(
        id="acc-1",
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        password_hash=_hash_password("oldpassword"),
        is_active=True,
        created_at=datetime.now(UTC),
    )


def _request(cookie: str = "") -> Request:
    headers = [(b"x-rag-request", b"1")]
    if cookie:
        headers.append((b"cookie", f"rag_session={cookie}".encode()))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/change-password",
            "headers": headers,
            "query_string": b"",
        }
    )


def _db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.mark.asyncio
async def test_update_profile_trims_and_saves_names():
    account = _account()
    db = _db()

    response = await update_profile(
        ProfileUpdateRequest(first_name="  Janet  ", last_name="  Smith "),
        account=account,
        db=db,
    )

    assert response.first_name == "Janet"
    assert response.last_name == "Smith"
    assert account.first_name == "Janet"
    assert account.last_name == "Smith"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_profile_rejects_blank_names():
    with pytest.raises(HTTPException) as exc:
        await update_profile(
            ProfileUpdateRequest(first_name="   ", last_name="Doe"),
            account=_account(),
            db=_db(),
        )

    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_change_password_rejects_wrong_current_password():
    account = _account()
    original_hash = account.password_hash

    with pytest.raises(HTTPException) as exc:
        await change_password(
            PasswordChangeRequest(current_password="not-my-password", new_password="Newpassword8!"),
            request=_request(),
            response=Response(),
            account=account,
            db=_db(),
        )

    assert exc.value.status_code == 400
    assert account.password_hash == original_hash


@pytest.mark.asyncio
async def test_change_password_rejects_short_password():
    with pytest.raises(HTTPException) as exc:
        await change_password(
            PasswordChangeRequest(current_password="oldpassword", new_password="short"),
            request=_request(),
            response=Response(),
            account=_account(),
            db=_db(),
        )

    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_change_password_updates_hash_and_rotates_session():
    account = _account()
    db = _db()

    response = await change_password(
        PasswordChangeRequest(current_password="oldpassword", new_password="Newpassword8!"),
        request=_request(cookie="a" * 43),
        response=Response(),
        account=account,
        db=db,
    )

    assert response.id == "acc-1"
    assert _verify_password("Newpassword8!", account.password_hash)
    assert not _verify_password("oldpassword", account.password_hash)
    assert account.last_login_at is not None
    db.commit.assert_awaited()
