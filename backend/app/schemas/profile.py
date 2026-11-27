from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ProfilePreferences(BaseModel):
    """User-facing settings shown on the profile page."""

    theme: Literal["light", "dark", "system"] = "system"
    email_notifications: bool = True
    default_persona_id: str | None = None


class ProfilePreferencesUpdate(BaseModel):
    """Partial preference update; unset fields keep their current value."""

    theme: Literal["light", "dark", "system"] | None = None
    email_notifications: bool | None = None
    default_persona_id: str | None = None


class ProfileDocument(BaseModel):
    id: str
    name: str
    mime_type: str | None = None
    size_bytes: int | None = None
    status: str
    chunks_created: int
    session_id: str
    session_title: str | None = None
    created_at: datetime
    processed_at: datetime | None = None
    expires_at: datetime


class ProfileStats(BaseModel):
    total_documents: int = 0
    total_sessions: int = 0
    total_chunks: int = 0
    total_queries: int = 0
    storage_bytes: int = 0
    documents_by_status: dict[str, int] = Field(default_factory=dict)


class ProfileResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    full_name: str
    email: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None
    preferences: ProfilePreferences
    stats: ProfileStats
    documents: list[ProfileDocument] = Field(default_factory=list)
