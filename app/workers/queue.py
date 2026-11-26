"""Postgres-backed ingestion queue with row-level leases."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select, update

from app.config.env_config import get_settings
from app.db.database import async_session
from app.db.models import Document, IngestJob
from app.utils.logger import logger


async def _claim_ingest_job() -> dict[str, Any] | None:
    now = datetime.now(UTC)
    stale_before = now - timedelta(minutes=get_settings().ingest_worker_lease_minutes)
    eligible = or_(
        IngestJob.status == "queued",
        (IngestJob.status == "processing")
        & or_(IngestJob.locked_at.is_(None), IngestJob.locked_at < stale_before),
    )
    async with async_session() as session:
        exhausted_result = await session.execute(
            select(IngestJob)
            .where(
                IngestJob.status == "processing",
                IngestJob.attempts >= 3,
                or_(IngestJob.locked_at.is_(None), IngestJob.locked_at < stale_before),
            )
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        exhausted = exhausted_result.scalar_one_or_none()
        if exhausted:
            exhausted.status = "failed"
            exhausted.locked_at = None
            exhausted.completed_at = now
            exhausted.error = exhausted.error or "Worker lease expired after maximum attempts"
            doc_result = await session.execute(
                select(Document).where(Document.id == exhausted.document_id)
            )
            doc = doc_result.scalar_one_or_none()
            if doc:
                doc.status = "failed"
                doc.error = exhausted.error
            await session.commit()
            return None

        result = await session.execute(
            select(IngestJob)
            .where(eligible, IngestJob.attempts < 3)
            .order_by(IngestJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = result.scalar_one_or_none()
        if job is None:
            return None
        doc_result = await session.execute(select(Document).where(Document.id == job.document_id))
        doc = doc_result.scalar_one_or_none()
        if doc is None:
            job.status = "failed"
            job.error = "Document record missing"
            job.completed_at = now
            await session.commit()
            return None

        job.status = "processing"
        job.locked_at = now
        job.attempts += 1
        doc.status = "processing"
        await session.commit()
        stored = doc.metadata_ or {}
        return {
            "document_id": job.document_id,
            "session_id": job.session_id,
            "user_id": job.user_id,
            "job_id": job.job_id,
            "storage_metadata": stored.get("storage"),
            "filename": stored.get("uploaded_filename", "document"),
            "content_type": stored.get("mime_type"),
            "metadata": stored.get("ingest_metadata", {}),
            "attempt": job.attempts,
        }


async def _renew_lease(job_id: str) -> None:
    lease_seconds = get_settings().ingest_worker_lease_minutes * 60
    while True:
        await asyncio.sleep(max(5, lease_seconds // 3))
        async with async_session() as session:
            await session.execute(
                update(IngestJob)
                .where(IngestJob.job_id == job_id, IngestJob.status == "processing")
                .values(locked_at=datetime.now(UTC))
            )
            await session.commit()


async def consume_ingest_jobs() -> None:
    """Poll durable jobs; multiple replicas coordinate through SKIP LOCKED."""
    from app.workers.tasks.ingest_document import run_ingest_task

    while True:
        try:
            payload = await _claim_ingest_job()
            if payload is None:
                await asyncio.sleep(get_settings().worker_poll_interval_seconds)
                continue
            heartbeat = asyncio.create_task(_renew_lease(payload["job_id"]))
            try:
                await run_ingest_task(**payload)
            finally:
                heartbeat.cancel()
                try:
                    await heartbeat
                except asyncio.CancelledError:
                    pass
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ingestion queue poll failed")
            await asyncio.sleep(max(1.0, get_settings().worker_poll_interval_seconds))
