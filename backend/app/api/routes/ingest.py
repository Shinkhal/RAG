import uuid
from contextlib import suppress

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import current_user_id
from app.clients.cloudinary_storage import cloudinary_storage_client
from app.clients.redis_cache import redis_cache
from app.config.env_config import get_settings
from app.db import get_session
from app.db.models import Document, IngestJob
from app.repositories.supabase_repo import SupabaseRepo
from app.schemas.ingest import DocumentResponse, IngestResponse, IngestStatusResponse
from app.services.chunking import SUPPORTED_MIME_TYPES, is_supported_file

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse, status_code=202)
async def ingest_document(
    session_id: str = Form(...),
    file: UploadFile = File(...),
    user_id: str = Depends(current_user_id),
    metadata: dict | None = None,
    session: AsyncSession = Depends(get_session),
) -> IngestResponse:
    """Accept a document for ingestion and return immediately.

    The upload is persisted before the durable database queue acknowledges it.
    Clients should poll
    ``GET /ingest/status/{job_id}`` to track progress.
    """
    if not is_supported_file(file.content_type, file.filename):
        supported = ", ".join(SUPPORTED_MIME_TYPES.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{file.content_type}'. Supported: {supported}",
        )

    repo = SupabaseRepo(session)
    if not await repo.get_session(session_id, user_id):
        raise HTTPException(status_code=404, detail="Session not found")

    settings = get_settings()

    # Apply a bounded size to every supported type before buffering or storing it.
    max_size_mb = settings.max_upload_size_mb
    if file.content_type == "application/pdf" or (file.filename or "").lower().endswith(".pdf"):
        max_size_mb = min(max_size_mb, settings.max_pdf_size_mb)
        max_size_bytes = max_size_mb * 1024 * 1024

        if file.size and file.size > max_size_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"PDF file size exceeds the limit of {max_size_mb} MB",
            )

    rate_limit_key = f"rate_limit:upload:{user_id}"
    if not await redis_cache.increment_rate_limit(rate_limit_key, settings.max_uploads_per_hour, 3600):
        raise HTTPException(
            status_code=429,
            detail=f"Too many uploads. Limit is {settings.max_uploads_per_hour} per hour.",
        )

    # ── Read file data and validate actual size ───────────────────────
    max_size_bytes = max_size_mb * 1024 * 1024
    file_data = await file.read(max_size_bytes + 1)
    if len(file_data) > max_size_bytes:
        raise HTTPException(status_code=413, detail=f"Upload exceeds the {max_size_mb} MB limit")

    # ── Create DB records synchronously so the IDs exist ─────────────
    document_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    filename = file.filename or "document"
    storage_metadata = None
    try:
        storage_metadata = await cloudinary_storage_client.upload_document(
            user_id=user_id,
            document_id=document_id,
            file_data=file_data,
            filename=filename,
            content_type=file.content_type,
        )
        doc = Document(
            id=document_id,
            user_id=user_id,
            session_id=session_id,
            status="queued",
            embed_version=settings.embedding_model,
            metadata_={
                "storage": storage_metadata,
                "uploaded_filename": filename,
                "mime_type": file.content_type,
                "ingest_metadata": metadata or {},
            },
        )
        job = IngestJob(
            job_id=job_id,
            document=doc,
            session_id=session_id,
            user_id=user_id,
            status="queued",
        )
        session.add(job)
        await session.commit()
    except Exception:
        await session.rollback()
        if storage_metadata:
            with suppress(Exception):
                await cloudinary_storage_client.delete_document_asset(storage_metadata)
        raise

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
    user_id: str = Depends(current_user_id),
    session: AsyncSession = Depends(get_session),
) -> IngestStatusResponse:
    from sqlalchemy import select

    stmt = select(IngestJob).where(IngestJob.job_id == job_id, IngestJob.user_id == user_id)
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check ownership before returning a cache hit. The cache is keyed by job
    # ID, not by user ID.
    cached = await redis_cache.get_cached_job_status(job_id)
    if cached:
        return IngestStatusResponse(**cached)

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
    user_id: str = Depends(current_user_id),
    session: AsyncSession = Depends(get_session),
) -> DocumentResponse:
    repo = SupabaseRepo(session)
    doc = await repo.get_document(document_id, user_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # The document cache is keyed only by document ID, so check ownership in
    # the database before serving cached metadata.
    cached = await redis_cache.get_cached_document(document_id)
    if cached:
        return DocumentResponse(**cached)

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
