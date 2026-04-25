"""Background task for async document ingestion."""

from datetime import datetime, timezone

from app.clients.redis_cache import redis_cache
from app.db.database import async_session
from app.db.models import Document
from app.repositories.supabase_repo import SupabaseRepo
from app.services.ingestion import process_ingest_job
from app.utils.logger import logger


async def run_ingest_task(
    document_id: str,
    session_id: str,
    user_id: str,
    job_id: str,
    file_data: bytes,
    filename: str,
    content_type: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Process document ingestion in the background.

    This function runs outside of the original HTTP request context.
    It opens its own database session, processes the document, and
    updates both the document and job records with the result.
    """
    metadata = metadata or {}

    async with async_session() as session:
        repo = SupabaseRepo(session)

        try:
            await repo.update_job_status(job_id, "processing")

            # Update document status to processing
            doc = await repo.get_document(document_id, user_id)
            if doc:
                doc.status = "processing"
                await session.commit()

            ingest_result = await process_ingest_job(
                document_id=document_id,
                session_id=session_id,
                user_id=user_id,
                file_data=file_data,
                filename=filename,
                content_type=content_type,
                metadata=metadata,
                repo=repo,
            )

            chunks_created = ingest_result.chunks_created
            storage_metadata = ingest_result.storage_metadata

            # Re-fetch document to update (session may have expired the reference)
            doc = await repo.get_document(document_id, user_id)
            if doc:
                doc.status = "processed"
                doc.chunks_created = chunks_created
                doc.processed_at = datetime.now(timezone.utc)
                doc.metadata_ = {
                    **(doc.metadata_ or {}),
                    "storage": storage_metadata,
                    "uploaded_filename": filename,
                    "mime_type": content_type,
                }
                await session.commit()

            await repo.update_job_status(job_id, "processed", chunks_created)

            logger.info(
                "Background ingest completed: doc=%s job=%s chunks=%d",
                document_id,
                job_id,
                chunks_created,
            )

        except Exception as e:
            logger.error(
                "Background ingest failed: doc=%s job=%s error=%s",
                document_id,
                job_id,
                str(e),
                exc_info=True,
            )

            # Re-fetch and mark as failed
            try:
                doc = await repo.get_document(document_id, user_id)
                if doc:
                    doc.status = "failed"
                    doc.error = str(e)
                    await session.commit()

                await repo.update_job_status(job_id, "failed", error=str(e))
            except Exception as update_err:
                logger.error(
                    "Failed to update error status: doc=%s error=%s",
                    document_id,
                    str(update_err),
                )

        finally:
            # Always bust caches so clients see the latest state
            await redis_cache.delete_cached_job_status(job_id)
            await redis_cache.delete_cached_document(document_id)
