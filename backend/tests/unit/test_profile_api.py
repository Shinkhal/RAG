"""Tests for the consolidated profile endpoint and preference updates."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from starlette.responses import Response

from app.api.routes.profile import (
    _current_preferences,
    _to_profile_document,
    get_profile,
    update_profile_preferences,
)
from app.db.models import Account, Document
from app.schemas.profile import ProfilePreferencesUpdate


class _Result:
    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows

    def all(self) -> list[tuple]:
        return self._rows


class _FakeDb:
    """Minimal async session that replays scripted query results."""

    def __init__(
        self,
        status_rows: list[tuple],
        scalars: list[int],
        document_rows: list[tuple],
    ) -> None:
        self._status_rows = status_rows
        self._scalars = list(scalars)
        self._document_rows = document_rows
        self.commit = AsyncMock()

    async def execute(self, _statement) -> _Result:
        if self._status_rows is not None:
            rows, self._status_rows = self._status_rows, None
            return _Result(rows)
        return _Result(self._document_rows)

    async def scalar(self, _statement) -> int:
        return self._scalars.pop(0)


def _account(preferences: dict | None = None) -> Account:
    now = datetime.now(UTC)
    return Account(
        id="acc-1",
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        password_hash="pbkdf2_sha256$1$00$00",
        preferences=preferences or {},
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _document() -> Document:
    now = datetime.now(UTC)
    return Document(
        id="doc-1",
        user_id="acc-1",
        session_id="session-1",
        status="processed",
        chunks_created=4,
        metadata_={
            "uploaded_filename": "notes.pdf",
            "mime_type": "application/pdf",
            "storage": {"bytes": 2048, "content_type": "application/pdf"},
        },
        created_at=now,
        expires_at=now,
    )


def test_current_preferences_falls_back_to_defaults() -> None:
    assert _current_preferences(_account()).theme == "system"
    assert _current_preferences(_account()).email_notifications is True


def test_current_preferences_merges_stored_values() -> None:
    preferences = _current_preferences(
        _account({"theme": "dark", "default_persona_id": "tutor"})
    )

    assert preferences.theme == "dark"
    assert preferences.default_persona_id == "tutor"
    assert preferences.email_notifications is True


def test_current_preferences_ignores_invalid_stored_values() -> None:
    preferences = _current_preferences(_account({"theme": "neon"}))

    assert preferences.theme == "system"


def test_current_preferences_keeps_other_values_when_one_is_invalid() -> None:
    preferences = _current_preferences(
        _account({"theme": "neon", "email_notifications": False})
    )

    assert preferences.theme == "system"
    assert preferences.email_notifications is False


def test_to_profile_document_extracts_upload_metadata() -> None:
    document = _to_profile_document(_document(), "Physics notebook")

    assert document.name == "notes.pdf"
    assert document.mime_type == "application/pdf"
    assert document.size_bytes == 2048
    assert document.session_title == "Physics notebook"


def test_to_profile_document_tolerates_malformed_size() -> None:
    document = _document()
    document.metadata_ = {"storage": {"bytes": "2 MB"}}

    assert _to_profile_document(document, None).size_bytes is None


@pytest.mark.asyncio
async def test_get_profile_returns_account_documents_and_stats() -> None:
    db = _FakeDb(
        status_rows=[("processed", 2), ("failed", 1)],
        scalars=[3, 12, 7, 4096],
        document_rows=[(_document(), "Physics notebook")],
    )

    profile = await get_profile(
        response=Response(),
        limit=100,
        account=_account({"theme": "dark"}),
        db=db,  # type: ignore[arg-type]
    )

    assert profile.full_name == "Jane Doe"
    assert profile.preferences.theme == "dark"
    assert profile.stats.total_documents == 3
    assert profile.stats.total_sessions == 3
    assert profile.stats.total_chunks == 12
    assert profile.stats.total_queries == 7
    assert profile.stats.storage_bytes == 4096
    assert profile.stats.documents_by_status == {"processed": 2, "failed": 1}
    assert profile.documents[0].name == "notes.pdf"


@pytest.mark.asyncio
async def test_update_preferences_preserves_unset_values() -> None:
    account = _account({"theme": "system", "email_notifications": False})
    db = AsyncMock()

    updated = await update_profile_preferences(
        ProfilePreferencesUpdate(theme="dark"),
        account=account,
        db=db,
    )

    assert updated.theme == "dark"
    assert updated.email_notifications is False
    assert account.preferences["theme"] == "dark"
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_preferences_ignores_explicit_nulls_for_required_fields() -> None:
    account = _account(
        {"theme": "dark", "email_notifications": False, "default_persona_id": "tutor"}
    )
    db = AsyncMock()

    updated = await update_profile_preferences(
        ProfilePreferencesUpdate(theme=None, email_notifications=None, default_persona_id=None),
        account=account,
        db=db,
    )

    assert updated.theme == "dark"
    assert updated.email_notifications is False
    # A null persona is a valid way to clear the preference.
    assert updated.default_persona_id is None
    assert account.preferences == {
        "theme": "dark",
        "email_notifications": False,
        "default_persona_id": None,
    }
