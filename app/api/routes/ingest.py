import asyncio
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.redis_cache import redis_cache
from app.config.env_config import get_settings
from app.db import get_session
from app.db.models import Document, IngestJob
from app.repositories.supabase_repo import SupabaseRepo
from app.schemas.ingest import DocumentResponse, IngestResponse, IngestStatusResponse
from app.services.chunking import SUPPORTED_MIME_TYPES, is_supported_file
from app.workers.tasks.ingest_document import run_ingest_task

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse, status_code=202)
async def ingest_document(
    user_id: str = Form(...),
    session_id: str = Form(...),
    file: UploadFile = File(...),
    metadata: dict | None = None,
    session: AsyncSession = Depends(get_session),
) -> IngestResponse:
    """Accept a document for ingestion and return immediately.

    The actual processing (upload, extract, embed, store) happens
    in a background asyncio task.  Clients should poll
    ``GET /ingest/status/{job_id}`` to track progress.
    """
    if not is_supported_file(file.content_type, file.filename):
        supported = ", ".join(SUPPORTED_MIME_TYPES.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Supported: {supported}",
        )

    settings = get_settings()

    # ── PDF-specific validations ──────────────────────────────────────
    if file.content_type == "application/pdf":
        max_size_mb = settings.max_pdf_size_mb
        max_size_bytes = max_size_mb * 1024 * 1024

        if file.size and file.size > max_size_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"PDF file size exceeds the limit of {max_size_mb} MB",
            )

        rate_limit_key = f"rate_limit:pdf_upload:{user_id}"
        max_uploads = settings.max_pdf_uploads_per_hour
        is_allowed = await redis_cache.increment_rate_limit(rate_limit_key, max_uploads, 3600)

        if not is_allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Too many PDF uploads. Limit is {max_uploads} per hour.",
            )

    # ── Read file data and validate actual size ───────────────────────
    file_data = await file.read()

    if file.content_type == "application/pdf":
        max_size_bytes = settings.max_pdf_size_mb * 1024 * 1024
        if len(file_data) > max_size_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"PDF file size exceeds the limit of {settings.max_pdf_size_mb} MB",
            )

    # ── Create DB records synchronously so the IDs exist ─────────────
    document_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    repo = SupabaseRepo(session)

    doc = Document(
        id=document_id,
        user_id=user_id,
        session_id=session_id,
        status="queued",
        metadata_=metadata or {},
    )
    await repo.upsert_document(doc)

    job = IngestJob(
        job_id=job_id,
        document_id=document_id,
        session_id=session_id,
        user_id=user_id,
        status="queued",
    )
    await repo.create_ingest_job(job)

    # ── Kick off background processing ────────────────────────────────
    asyncio.create_task(
        run_ingest_task(
            document_id=document_id,
            session_id=session_id,
            user_id=user_id,
            job_id=job_id,
            file_data=file_data,
            filename=file.filename or "document.pdf",
            content_type=file.content_type,
            metadata=metadata or {},
        )
    )

    return IngestResponse(
        document_id=document_id,
        job_id=job_id,
        status="queued",
        chunks_created=0,
        processing_time_ms=None,
    )


@router.get("/ingest/status/{job_id}", response_model=IngestStatusResponse)
async def get_ingest_status(
    job_id: str,
    user_id: str,
    session: AsyncSession = Depends(get_session),
) -> IngestStatusResponse:
    cached = await redis_cache.get_cached_job_status(job_id)
    if cached:
        return IngestStatusResponse(**cached)

    from sqlalchemy import select

    stmt = select(IngestJob).where(IngestJob.job_id == job_id, IngestJob.user_id == user_id)
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    response = IngestStatusResponse(
        job_id=job.job_id,
        document_id=job.document_id,
        status=job.status,
        chunks_created=job.chunks_created,
        error=job.error,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )
    await redis_cache.cache_job_status(job_id, response.model_dump(mode="json"))
    return response


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    user_id: str,
    session: AsyncSession = Depends(get_session),
) -> DocumentResponse:
    cached = await redis_cache.get_cached_document(document_id)
    if cached:
        return DocumentResponse(**cached)

    repo = SupabaseRepo(session)
    doc = await repo.get_document(document_id, user_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    response = DocumentResponse(
        id=doc.id,
        user_id=doc.user_id,
        status=doc.status,
        chunks_created=doc.chunks_created,
        error=doc.error,
        metadata=doc.metadata_,
        created_at=doc.created_at,
        processed_at=doc.processed_at,
    )
    await redis_cache.cache_document(document_id, response.model_dump(mode="json"))
    return response
