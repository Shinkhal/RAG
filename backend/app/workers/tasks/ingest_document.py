"""Background task for async document ingestion."""

from datetime import UTC, datetime

from app.clients.cloudinary_storage import cloudinary_storage_client
from app.clients.redis_cache import redis_cache
from app.config.env_config import get_settings
from app.db.database import async_session
from app.repositories.supabase_repo import SupabaseRepo
from app.services.ingestion import process_ingest_job
from app.utils.logger import logger


async def run_ingest_task(
    document_id: str,
    session_id: str,
    user_id: str,
    job_id: str,
    filename: str,
    content_type: str | None = None,
    metadata: dict | None = None,
    storage_metadata: dict | None = None,
    attempt: int = 1,
) -> None:
    """Process document ingestion in the background.

    This function runs outside of the original HTTP request context.
    It opens its own database session, processes the document, and
    updates both the document and job records with the result.
    """
    metadata = metadata or {}
    retry_delay = 0

    async with async_session() as session:
        repo = SupabaseRepo(session)

        try:
            if not storage_metadata:
                raise ValueError("Ingestion job has no persisted upload metadata")
            file_data = await cloudinary_storage_client.download_document(
                storage_metadata,
                max_bytes=get_settings().max_upload_size_mb * 1024 * 1024,
            )
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
                storage_metadata=storage_metadata,
                repo=repo,
            )

            chunks_created = ingest_result.chunks_created
            storage_metadata = ingest_result.storage_metadata

            # Re-fetch document to update (session may have expired the reference)
            doc = await repo.get_document(document_id, user_id)
            if doc:
                doc.status = "processed"
                doc.chunks_created = chunks_created
                doc.embed_version = get_settings().embedding_model
                doc.processed_at = datetime.now(UTC)
                doc.metadata_ = {
                    **(doc.metadata_ or {}),
                    "storage": storage_metadata,
                    "uploaded_filename": filename,
                    "mime_type": content_type,
                    "extraction_report": ingest_result.extraction_report,
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
            retrying = attempt < 3
            retry_delay = 2 ** attempt if retrying else 0
            try:
                await session.rollback()
                doc = await repo.get_document(document_id, user_id)
                if doc:
                    doc.status = "queued" if retrying else "failed"
                    doc.error = str(e)
                    await session.commit()

                await repo.update_job_status(
                    job_id, "queued" if retrying else "failed", error=str(e)
                )
            except Exception as update_err:
                logger.error(
                    "Failed to update error status: doc=%s error=%s",
                    document_id,
                    str(update_err),
                )

        finally:
            # Always bust caches so clients see the latest state. Cache
            # failures must not take down the ingestion worker.
            try:
                await redis_cache.delete_cached_job_status(job_id)
            except Exception:
                logger.warning("Failed to clear job status cache: job=%s", job_id, exc_info=True)
            try:
                await redis_cache.delete_cached_document(document_id)
            except Exception:
                logger.warning(
                    "Failed to clear document cache: doc=%s", document_id, exc_info=True
                )

    if retry_delay:
        import asyncio

        await asyncio.sleep(retry_delay)
