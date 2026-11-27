from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.auth import (
    ForgotPasswordRequest,
    ResetPasswordRequest,
    _hash_password,
    _token_hash,
    _verify_password,
    forgot_password,
    reset_password,
)
from app.db.models import Account, PasswordResetToken
from app.services.email import render_email_template


@pytest.mark.asyncio
async def test_forgot_password_unknown_email_returns_generic_message():
    db = AsyncMock()
    db.scalar.return_value = None

    res = await forgot_password(ForgotPasswordRequest(email="nobody@example.com"), db=db)

    assert "If an account exists" in res.message
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_forgot_password_sends_email_with_reset_link():
    account = Account(
        id="acc-1",
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        password_hash=_hash_password("oldpass123"),
        is_active=True,
    )
    db = AsyncMock()
    db.scalar.return_value = account
    db.add = MagicMock()

    with patch("app.api.auth.send_password_reset_email", new_callable=AsyncMock) as mock_send:
        res = await forgot_password(ForgotPasswordRequest(email="Jane@Example.com"), db=db)

    assert "If an account exists" in res.message
    db.add.assert_called_once()
    added_token = db.add.call_args[0][0]
    assert isinstance(added_token, PasswordResetToken)
    assert added_token.account_id == "acc-1"
    mock_send.assert_awaited_once()
    call_kwargs = mock_send.await_args.kwargs
    assert call_kwargs["to_email"] == "jane@example.com"
    assert call_kwargs["first_name"] == "Jane"
    assert "/reset-password?token=" in call_kwargs["reset_url"]


@pytest.mark.asyncio
async def test_reset_password_updates_hash_and_marks_token_used():
    raw_token = "sample-reset-token-123456"
    reset_record = PasswordResetToken(
        token_hash=_token_hash(raw_token),
        account_id="acc-1",
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
        used_at=None,
    )
    account = Account(
        id="acc-1",
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        password_hash=_hash_password("oldpass123"),
        is_active=True,
    )
    db = AsyncMock()
    db.scalar.side_effect = [reset_record, account]

    res = await reset_password(
        ResetPasswordRequest(token=raw_token, password="Newpassword8!"), db=db
    )

    assert "reset" in res.message.lower()
    assert reset_record.used_at is not None
    assert _verify_password("Newpassword8!", account.password_hash)
    assert not _verify_password("oldpass123", account.password_hash)


@pytest.mark.asyncio
async def test_reset_password_rejects_short_password():
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc:
        await reset_password(
            ResetPasswordRequest(token="sample-reset-token-123456", password="short"), db=db
        )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_reset_password_rejects_invalid_token():
    db = AsyncMock()
    db.scalar.return_value = None
    with pytest.raises(HTTPException) as exc:
        await reset_password(
            ResetPasswordRequest(token="invalid-token-123456", password="Validpass8!"), db=db
        )
    assert exc.value.status_code == 400


def test_email_templates_render_with_escaping():
    templates = [
        ("password_reset", {"first_name": "<Jane>", "reset_url": "https://app.test/reset?token=abc", "expires_minutes": 30}),
        ("welcome", {"first_name": "Jane", "workspace_url": "https://app.test/workspace"}),
        ("password_changed", {"first_name": "Jane", "login_url": "https://app.test/login"}),
        ("usage_alert", {"first_name": "Jane", "summary": "80% used", "uploads_used": 16, "uploads_limit": 20, "workspace_url": "https://app.test/workspace"}),
        ("document_processed", {"first_name": "Jane", "document_name": "notes.pdf", "status_label": "ready", "notebook_title": "Research", "workspace_url": "https://app.test/workspace"}),
    ]
    for name, ctx in templates:
        text_body, html_body = render_email_template(name, ctx)
        assert text_body.strip()
        assert "RAG Workspace" in html_body
    _, reset_html = render_email_template(
        "password_reset",
        {"first_name": "<script>alert(1)</script>", "reset_url": "https://app.test/reset?token=abc", "expires_minutes": 30},
    )
    assert "<script>" not in reset_html
    assert "&lt;script&gt;" in reset_html
