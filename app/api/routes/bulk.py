import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.cloudinary_storage import cloudinary_storage_client, extract_storage_metadata
from app.clients.redis_cache import redis_cache
from app.db import get_session
from app.db.models import IngestJob
from app.repositories.supabase_repo import SupabaseRepo
from app.schemas.ingest import DeleteResponse

router = APIRouter()


async def _delete_document_asset(doc) -> None:
    storage_metadata = extract_storage_metadata(doc.metadata_)
    if storage_metadata:
        await cloudinary_storage_client.delete_document_asset(storage_metadata)


@router.delete("/documents/{document_id}", response_model=DeleteResponse)
async def delete_document(
    document_id: str,
    user_id: str,
    session: AsyncSession = Depends(get_session),
) -> DeleteResponse:
    repo = SupabaseRepo(session)
    doc = await repo.get_document(document_id, user_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    await _delete_document_asset(doc)
    deleted = await repo.delete_document(document_id, user_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")

    await redis_cache.delete_cached_document(document_id)
    await redis_cache.delete_document_context(document_id)

    return DeleteResponse(document_id=document_id, deleted=True)


@router.post("/bulk-delete")
async def bulk_delete_documents(
    document_ids: list[str],
    user_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, int]:
    repo = SupabaseRepo(session)
    deleted_count = 0

    for doc_id in document_ids:
        doc = await repo.get_document(doc_id, user_id)
        if not doc:
            continue

        await _delete_document_asset(doc)

        if await repo.delete_document(doc_id, user_id):
            deleted_count += 1
            await redis_cache.delete_cached_document(doc_id)
            await redis_cache.delete_document_context(doc_id)

    return {"deleted": deleted_count, "total_requested": len(document_ids)}


@router.post("/reindex/{document_id}")
async def reindex_document(
    document_id: str,
    user_id: str,
    session: AsyncSession = Depends(get_session),
):
    repo = SupabaseRepo(session)
    doc = await repo.get_document(document_id, user_id)

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    in_progress = await session.execute(
        select(IngestJob.job_id).where(
            IngestJob.document_id == document_id,
            IngestJob.status.in_(["queued", "processing"]),
        ).limit(1)
    )
    if in_progress.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Document ingestion is already in progress")

    doc.status = "queued"
    doc.error = None
    doc.metadata_ = {
        **(doc.metadata_ or {}),
        "extraction_report": None,
    }
    job = IngestJob(
        job_id=str(uuid.uuid4()),
        document_id=doc.id,
        session_id=doc.session_id,
        user_id=user_id,
        status="queued",
    )
    session.add(job)
    await session.commit()
    await redis_cache.delete_cached_document(document_id)
    await redis_cache.delete_document_context(document_id)
    return {"message": "Reindex queued", "document_id": document_id, "job_id": job.job_id}
