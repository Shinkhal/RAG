import importlib
from types import SimpleNamespace
from typing import cast

import pytest

import app.clients.cloudinary_storage as storage_module
from app.repositories.supabase_repo import SupabaseRepo
from app.services import ingestion as ingestion_module


@pytest.mark.asyncio
async def test_process_ingest_job_uploads_before_extracting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    redis_module = importlib.import_module("app.clients.redis_cache")

    async def fake_set_document_context(document_id: str, context: dict) -> None:
        return None

    class FakeStorageClient:
        async def upload_document(
            self,
            user_id: str,
            document_id: str,
            file_data: bytes,
            filename: str,
            content_type: str | None = None,
        ) -> dict[str, object]:
            calls.append("upload")
            return {
                "provider": "cloudinary",
                "public_id": f"documents/{user_id}/{document_id}",
                "resource_type": "raw",
                "secure_url": "https://example.com/doc.pdf",
                "folder": f"documents/{user_id}",
            }

        async def delete_document_asset(self, metadata: dict[str, object] | None) -> bool:
            calls.append("cleanup")
            return True

    async def fake_embed_documents(texts: list[str]) -> list[list[float]]:
        calls.append("embed")
        return [[1.0] for _ in texts]

    def fake_extract_text(file_data: bytes, content_type: str | None = None, filename: str | None = None) -> str:
        calls.append("extract")
        return "hello world"

    def fake_normalize_document_text(text: str) -> str:
        calls.append("clean")
        return text

    def fake_sliding_window_chunks(text: str) -> list[str]:
        calls.append("chunk")
        return ["chunk-a", "chunk-b"]

    class FakeRepo:
        def __init__(self) -> None:
            self.saved_chunks: list[object] = []

        async def upsert_chunks(self, chunks: list[object]) -> int:
            calls.append("persist")
            self.saved_chunks = chunks
            return len(chunks)

    monkeypatch.setattr(ingestion_module, "cloudinary_storage_client", FakeStorageClient())
    monkeypatch.setattr(
        ingestion_module, "gemini_client", SimpleNamespace(embed_documents=fake_embed_documents)
    )
    monkeypatch.setattr(ingestion_module, "extract_text", fake_extract_text)
    monkeypatch.setattr(
        ingestion_module, "normalize_document_text", fake_normalize_document_text
    )
    monkeypatch.setattr(ingestion_module, "sliding_window_chunks", fake_sliding_window_chunks)
    monkeypatch.setattr(redis_module.redis_cache, "set_document_context", fake_set_document_context)

    repo = cast(SupabaseRepo, FakeRepo())
    ingest_result = await ingestion_module.process_ingest_job(
        document_id="doc-123",
        session_id="session-1",
        user_id="user-1",
        file_data=b"hello world plain text",
        filename="report.txt",
        repo=repo,
        content_type="text/plain",
        metadata={"source": "upload"},
    )

    assert ingest_result.chunks_created == 2
    assert ingest_result.storage_metadata["provider"] == "cloudinary"
    assert ingest_result.storage_metadata["public_id"] == "documents/user-1/doc-123"
    assert calls[0] == "upload"
    assert calls.index("upload") < calls.index("extract")
    assert repo.saved_chunks is not None
    assert len(repo.saved_chunks) == 2


@pytest.mark.asyncio
async def test_process_ingest_job_raises_on_embedding_count_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    redis_module = importlib.import_module("app.clients.redis_cache")

    async def fake_set_document_context(document_id: str, context: dict) -> None:
        return None

    class FakeStorageClient:
        async def upload_document(
            self,
            user_id: str,
            document_id: str,
            file_data: bytes,
            filename: str,
            content_type: str | None = None,
        ) -> dict[str, object]:
            return {"provider": "cloudinary", "public_id": f"documents/{user_id}/{document_id}"}

        async def delete_document_asset(self, metadata: dict[str, object] | None) -> bool:
            return True

    async def fake_embed_documents(texts: list[str]) -> list[list[float]]:
        return [[1.0]]

    def fake_extract_text(
        file_data: bytes, content_type: str | None = None, filename: str | None = None
    ) -> str:
        return "hello world"

    def fake_normalize_document_text(text: str) -> str:
        return text

    def fake_sliding_window_chunks(text: str) -> list[str]:
        return ["chunk-a", "chunk-b"]

    class FakeRepo:
        async def upsert_chunks(self, chunks: list[object]) -> int:
            return len(chunks)

    monkeypatch.setattr(ingestion_module, "cloudinary_storage_client", FakeStorageClient())
    monkeypatch.setattr(
        ingestion_module, "gemini_client", SimpleNamespace(embed_documents=fake_embed_documents)
    )
    monkeypatch.setattr(ingestion_module, "extract_text", fake_extract_text)
    monkeypatch.setattr(ingestion_module, "normalize_document_text", fake_normalize_document_text)
    monkeypatch.setattr(ingestion_module, "sliding_window_chunks", fake_sliding_window_chunks)
    monkeypatch.setattr(redis_module.redis_cache, "set_document_context", fake_set_document_context)

    repo = cast(SupabaseRepo, FakeRepo())
    with pytest.raises(ValueError, match="Embedding count mismatch for text ingestion"):
        await ingestion_module.process_ingest_job(
            document_id="doc-123",
            session_id="session-1",
            user_id="user-1",
            file_data=b"hello world plain text",
            filename="report.txt",
            repo=repo,
            content_type="text/plain",
            metadata={"source": "upload"},
        )


@pytest.mark.asyncio
async def test_cloudinary_storage_client_normalizes_and_deletes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, object]] = []

    class FakeUploader:
        def upload(self, payload, **kwargs):
            calls.append(("upload", kwargs))
            assert payload.read() == b"%PDF-1.4"
            return {
                "public_id": "documents/user-1/doc-123",
                "asset_id": "asset-123",
                "version": 42,
                "resource_type": "raw",
                "format": "pdf",
                "secure_url": "https://example.com/doc.pdf",
                "url": "http://example.com/doc.pdf",
                "bytes": 8,
            }

        def destroy(self, public_id, **kwargs):
            calls.append(("destroy", {"public_id": public_id, **kwargs}))
            return {"result": "ok"}

    monkeypatch.setattr(
        storage_module, "_ensure_cloudinary_config", lambda: calls.append(("init", True))
    )
    monkeypatch.setattr(storage_module, "_get_uploader", lambda: FakeUploader())

    client = storage_module.CloudinaryStorageClient(folder_root="documents")
    upload_result = await client.upload_document(
        user_id="user-1",
        document_id="doc-123",
        file_data=b"%PDF-1.4",
        filename="report.pdf",
        content_type="application/pdf",
    )

    assert upload_result["provider"] == "cloudinary"
    assert upload_result["folder"] == "documents/user-1"
    assert upload_result["public_id"] == "documents/user-1/doc-123"
    assert upload_result["content_type"] == "application/pdf"
    assert calls[0] == ("init", True)
    assert calls[1][0] == "upload"

    deleted = await client.delete_document_asset({"storage": upload_result})
    assert deleted is True
    assert calls[-1][0] == "destroy"


@pytest.mark.asyncio
async def test_cloudinary_download_document_uses_private_download_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cloudinary.utils as cloudinary_utils

    requested_urls: list[str] = []

    monkeypatch.setattr(storage_module, "_ensure_cloudinary_config", lambda: None)
    monkeypatch.setattr(
        cloudinary_utils,
        "private_download_url",
        lambda public_id, fmt, resource_type="raw", type="authenticated", attachment=False: (
            f"https://api.cloudinary.com/v1_1/demo/{resource_type}/download?public_id={public_id}&type={type}&attachment={attachment}"
        ),
    )

    class FakeResponse:
        headers = {"content-length": "9"}

        def raise_for_status(self) -> None:
            return None

        async def aiter_bytes(self):
            yield b"pdf-bytes"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        def stream(self, method: str, url: str, follow_redirects: bool = True):
            requested_urls.append(url)
            return FakeResponse()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(storage_module.httpx, "AsyncClient", FakeAsyncClient)

    client = storage_module.CloudinaryStorageClient()
    data = await client.download_document(
        {
            "storage": {
                "provider": "cloudinary",
                "public_id": "documents/u1/doc-1.pdf",
                "resource_type": "raw",
                "type": "authenticated",
            }
        },
        max_bytes=1024,
    )

    assert data == b"pdf-bytes"
    assert len(requested_urls) == 1
    assert requested_urls[0].startswith("https://api.cloudinary.com/v1_1/demo/raw/download")


@pytest.mark.asyncio
async def test_cloudinary_download_retries_signed_url_after_401(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cloudinary.utils as cloudinary_utils
    import httpx

    requested_urls: list[str] = []

    monkeypatch.setattr(storage_module, "_ensure_cloudinary_config", lambda: None)
    monkeypatch.setattr(
        cloudinary_utils,
        "private_download_url",
        lambda public_id, fmt, resource_type="raw", type="authenticated", attachment=False: (
            f"https://api.cloudinary.com/v1_1/demo/{resource_type}/download?public_id={public_id}&attachment={attachment}"
        ),
    )

    async def fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(storage_module.asyncio, "sleep", fake_sleep)

    class FakeResponse:
        def __init__(self, url: str, status_code: int) -> None:
            self.url = url
            self.status_code = status_code
            self.headers = {"content-length": "9"}

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                request = httpx.Request("GET", self.url)
                response = httpx.Response(self.status_code, request=request)
                raise httpx.HTTPStatusError(
                    f"{self.status_code} error", request=request, response=response
                )

        async def aiter_bytes(self):
            yield b"pdf-bytes"

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        def stream(self, method: str, url: str, follow_redirects: bool = True):
            requested_urls.append(url)
            status = 401 if "attachment=False" in url else 200
            return FakeResponse(url, status)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(storage_module.httpx, "AsyncClient", FakeAsyncClient)

    client = storage_module.CloudinaryStorageClient()
    data = await client.download_document(
        {
            "provider": "cloudinary",
            "public_id": "documents/u1/doc-1.pdf",
            "resource_type": "raw",
            "type": "authenticated",
            "secure_url": "https://res.cloudinary.com/demo/raw/authenticated/doc-1.pdf",
        },
        max_bytes=1024,
    )

    assert data == b"pdf-bytes"
    assert len(requested_urls) == 2
    assert "attachment=True" in requested_urls[1]
