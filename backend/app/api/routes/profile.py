from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from pydantic import ValidationError
from sqlalchemy import BigInteger, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import current_account, protect_mutation
from app.db import get_session
from app.db.models import Account, ChatSession, Chunk, Document, QueryLog
from app.schemas.profile import (
    ProfileDocument,
    ProfilePreferences,
    ProfilePreferencesUpdate,
    ProfileResponse,
    ProfileStats,
)

router = APIRouter()

DEFAULT_DOCUMENT_LIMIT = 100
MAX_DOCUMENT_LIMIT = 500


def _current_preferences(account: Account) -> ProfilePreferences:
    """Merge stored preferences over the defaults, dropping invalid values.

    Values are validated one field at a time so a single bad entry (for example
    from an older release or a manual database edit) does not reset every other
    preference to its default.
    """
    defaults = ProfilePreferences()
    stored = account.preferences if isinstance(account.preferences, dict) else {}
    values = defaults.model_dump()

    for field in ProfilePreferences.model_fields:
        if field not in stored:
            continue
        try:
            validated = ProfilePreferences.model_validate({**values, field: stored[field]})
        except ValidationError:
            continue
        values[field] = getattr(validated, field)

    return ProfilePreferences.model_validate(values)


def _as_size(value: Any) -> int | None:
    """Coerce stored upload sizes into a non-negative integer when possible."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _to_profile_document(document: Document, session_title: str | None) -> ProfileDocument:
    metadata: dict[str, Any] = document.metadata_ or {}
    storage: dict[str, Any] = metadata.get("storage") or {}
    return ProfileDocument(
        id=document.id,
        name=metadata.get("uploaded_filename") or storage.get("original_filename") or document.id,
        mime_type=metadata.get("mime_type") or storage.get("content_type"),
        size_bytes=_as_size(storage.get("bytes")),
        status=document.status,
        chunks_created=document.chunks_created,
        session_id=document.session_id,
        session_title=session_title,
        created_at=document.created_at,
        processed_at=document.processed_at,
        expires_at=document.expires_at,
    )


async def _load_stats(db: AsyncSession, user_id: str) -> ProfileStats:
    status_rows = await db.execute(
        select(Document.status, func.count())
        .where(Document.user_id == user_id)
        .group_by(Document.status)
    )
    documents_by_status = {status: count for status, count in status_rows.all()}

    total_sessions = await db.scalar(
        select(func.count()).select_from(ChatSession).where(ChatSession.user_id == user_id)
    )
    total_chunks = await db.scalar(
        select(func.count()).select_from(Chunk).where(Chunk.user_id == user_id)
    )
    total_queries = await db.scalar(
        select(func.count()).select_from(QueryLog).where(QueryLog.user_id == user_id)
    )
    # Older or externally produced metadata may store sizes as strings. Guard
    # the cast so one malformed row cannot break the whole profile request.
    raw_bytes = Document.metadata_["storage"]["bytes"].astext
    numeric_bytes = case(
        (raw_bytes.regexp_match(r"^[0-9]+$"), func.cast(raw_bytes, BigInteger)),
        else_=0,
    )
    storage_bytes = await db.scalar(
        select(func.coalesce(func.sum(numeric_bytes), 0)).where(Document.user_id == user_id)
    )

    return ProfileStats(
        total_documents=sum(documents_by_status.values()),
        total_sessions=total_sessions or 0,
        total_chunks=total_chunks or 0,
        total_queries=total_queries or 0,
        storage_bytes=storage_bytes or 0,
        documents_by_status=documents_by_status,
    )


async def _load_documents(
    db: AsyncSession, user_id: str, limit: int
) -> list[ProfileDocument]:
    rows = await db.execute(
        select(Document, ChatSession.title)
        .join(ChatSession, ChatSession.id == Document.session_id)
        .where(Document.user_id == user_id)
        .order_by(Document.created_at.desc())
        .limit(limit)
    )
    return [
        _to_profile_document(document, session_title)
        for document, session_title in rows.all()
    ]


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(
    response: Response,
    limit: int = Query(
        default=DEFAULT_DOCUMENT_LIMIT,
        ge=1,
        le=MAX_DOCUMENT_LIMIT,
        description="Maximum number of uploaded documents to return.",
    ),
    account: Account = Depends(current_account),
    db: AsyncSession = Depends(get_session),
) -> ProfileResponse:
    """Return everything the profile page needs in a single request."""
    response.headers["Cache-Control"] = "no-store"

    stats = await _load_stats(db, account.id)
    documents = await _load_documents(db, account.id, limit)

    return ProfileResponse(
        id=account.id,
        first_name=account.first_name,
        last_name=account.last_name,
        full_name=f"{account.first_name} {account.last_name}".strip(),
        email=account.email,
        is_active=account.is_active,
        created_at=account.created_at,
        updated_at=account.updated_at,
        last_login_at=account.last_login_at,
        preferences=_current_preferences(account),
        stats=stats,
        documents=documents,
    )


@router.patch(
    "/profile/preferences",
    response_model=ProfilePreferences,
    dependencies=[Depends(protect_mutation)],
)
async def update_profile_preferences(
    data: ProfilePreferencesUpdate,
    account: Account = Depends(current_account),
    db: AsyncSession = Depends(get_session),
) -> ProfilePreferences:
    """Update one or more profile preferences, leaving the rest unchanged."""
    updates = data.model_dump(exclude_unset=True)

    # ``theme`` and ``email_notifications`` always have a value. Treat an
    # explicit null as "leave unchanged" instead of persisting an invalid value,
    # while still allowing ``default_persona_id`` to be cleared with null.
    for field in ("theme", "email_notifications"):
        if updates.get(field) is None:
            updates.pop(field, None)

    preferences = _current_preferences(account).model_dump()
    preferences.update(updates)

    account.preferences = preferences
    await db.commit()
    return _current_preferences(account)
