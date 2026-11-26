"""End-to-end ingestion tests with external services replaced by fakes.

These exercise the real extraction, chunking, and persistence orchestration in
``process_ingest_job`` without touching Cloudinary, Gemini, Redis, or Postgres.
"""

from __future__ import annotations

import importlib
from typing import Any, cast

import pytest

from app.repositories.supabase_repo import ChunkRecord, SupabaseRepo
from app.services import ingestion as ingestion_module


class FakeStorageClient:
    def __init__(self) -> None:
        self.uploads: list[dict[str, Any]] = []

    async def upload_document(
        self,
        user_id: str,
        document_id: str,
        file_data: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        self.uploads.append({"document_id": document_id, "filename": filename})
        return {
            "provider": "cloudinary",
            "public_id": f"documents/{user_id}/{document_id}",
            "resource_type": "raw",
            "type": "authenticated",
            "secure_url": "https://example.com/doc",
            "folder": f"documents/{user_id}",
        }

    async def delete_document_asset(self, metadata: dict[str, Any] | None) -> bool:
        return True


class FakeGeminiClient:
    def __init__(self) -> None:
        self.batches: list[list[str]] = []

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.batches.append(list(texts))
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeRepo:
    def __init__(self) -> None:
        self.saved_chunks: list[ChunkRecord] = []

    async def upsert_chunks(self, chunks: list[ChunkRecord]) -> int:
        self.saved_chunks = list(chunks)
        return len(chunks)


class FakeRedisCache:
    def __init__(self, *, fail: bool = False) -> None:
        self.contexts: list[dict[str, Any]] = []
        self.fail = fail

    async def set_document_context(self, document_id: str, context: dict[str, Any]) -> None:
        if self.fail:
            raise RuntimeError("redis unavailable")
        self.contexts.append({"document_id": document_id, **context})


def _patch_services(
    monkeypatch: pytest.MonkeyPatch,
    *,
    redis_fail: bool = False,
) -> tuple[FakeStorageClient, FakeGeminiClient, FakeRepo, FakeRedisCache]:
    storage = FakeStorageClient()
    gemini = FakeGeminiClient()
    repo = FakeRepo()
    redis_cache = FakeRedisCache(fail=redis_fail)
    redis_module = importlib.import_module("app.clients.redis_cache")

    monkeypatch.setattr(ingestion_module, "cloudinary_storage_client", storage)
    monkeypatch.setattr(ingestion_module, "gemini_client", gemini)
    monkeypatch.setattr(redis_module.redis_cache, "set_document_context", redis_cache.set_document_context)
    return storage, gemini, repo, redis_cache


def _make_pdf(text: str) -> bytes:
    fitz = pytest.importorskip("fitz")
    document = fitz.open()
    try:
        for _ in range(2):
            page = document.new_page()
            page.insert_text((72, 72), text, fontsize=8)
        return document.tobytes()
    finally:
        document.close()


@pytest.mark.asyncio
async def test_pdf_ingestion_chunks_every_page_and_caches_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, gemini, repo, redis_cache = _patch_services(monkeypatch)
    body = "Retrieval augmented generation connects documents to answers. " * 40
    pdf = _make_pdf(body)

    result = await ingestion_module.process_ingest_job(
        document_id="doc-pdf",
        session_id="session-1",
        user_id="user-1",
        file_data=pdf,
        filename="report.pdf",
        repo=cast(SupabaseRepo, repo),
        content_type="application/pdf",
        storage_metadata={"provider": "cloudinary", "public_id": "documents/u1/doc-pdf"},
    )

    assert result.chunks_created > 0
    assert result.extraction_report is not None
    assert result.extraction_report["page_count"] == 2
    assert len(repo.saved_chunks) == result.chunks_created
    assert {chunk.metadata["page"] for chunk in repo.saved_chunks} == {1, 2}
    assert all(chunk.content.strip() for chunk in repo.saved_chunks)
    assert sum(len(batch) for batch in gemini.batches) == result.chunks_created
    assert redis_cache.contexts
    assert "Retrieval augmented generation" in redis_cache.contexts[0]["full_text"]


@pytest.mark.asyncio
async def test_text_ingestion_persists_chunks_when_context_cache_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, gemini, repo, _ = _patch_services(monkeypatch, redis_fail=True)
    text = "The pipeline must still save chunks when the cache is unavailable. " * 60

    result = await ingestion_module.process_ingest_job(
        document_id="doc-text",
        session_id="session-1",
        user_id="user-1",
        file_data=text.encode("utf-8"),
        filename="notes.txt",
        repo=cast(SupabaseRepo, repo),
        content_type="text/plain",
        storage_metadata={"provider": "cloudinary", "public_id": "documents/u1/doc-text"},
    )

    assert result.chunks_created > 0
    assert len(repo.saved_chunks) == result.chunks_created
    assert sum(len(batch) for batch in gemini.batches) == result.chunks_created


@pytest.mark.asyncio
async def test_ingestion_rejects_documents_without_indexable_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_services(monkeypatch)

    with pytest.raises(ValueError, match="No indexable text"):
        await ingestion_module.process_ingest_job(
            document_id="doc-empty",
            session_id="session-1",
            user_id="user-1",
            file_data="●●●\n\n•••".encode("utf-8"),
            filename="symbols.txt",
            repo=cast(SupabaseRepo, FakeRepo()),
            content_type="text/plain",
            storage_metadata={"provider": "cloudinary", "public_id": "documents/u1/doc-empty"},
        )


@pytest.mark.asyncio
async def test_non_latin_document_is_indexed(monkeypatch: pytest.MonkeyPatch) -> None:
    _, _, repo, _ = _patch_services(monkeypatch)
    text = "यह एक हिंदी दस्तावेज़ है। " * 100

    result = await ingestion_module.process_ingest_job(
        document_id="doc-hindi",
        session_id="session-1",
        user_id="user-1",
        file_data=text.encode("utf-8"),
        filename="hindi.txt",
        repo=cast(SupabaseRepo, repo),
        content_type="text/plain",
        storage_metadata={"provider": "cloudinary", "public_id": "documents/u1/doc-hindi"},
    )

    assert result.chunks_created > 0
    assert repo.saved_chunks
