from datetime import datetime
from typing import Any

from pydantic import BaseModel


class IngestRequest(BaseModel):
    user_id: str
    metadata: dict[str, Any] | None = None


class IngestResponse(BaseModel):
    document_id: str
    status: str
    chunks_created: int = 0
    processing_time_ms: int | None = None


class IngestStatusResponse(BaseModel):
    job_id: str
    document_id: str
    status: str
    chunks_created: int
    error: str | None
    created_at: datetime
    completed_at: datetime | None = None


class DocumentResponse(BaseModel):
    id: str
    user_id: str
    status: str
    chunks_created: int
    error: str | None
    metadata: dict[str, Any]
    created_at: datetime
    processed_at: datetime | None = None


class DeleteResponse(BaseModel):
    document_id: str
    deleted: bool
