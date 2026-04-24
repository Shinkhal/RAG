from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from app.clients.cloudinary_storage import cloudinary_storage_client
from app.repositories.supabase_repo import SupabaseRepo, ChunkRecord
from app.services.chunking import sliding_window_chunks, batched, extract_text, clean_text
from app.clients.gemini import gemini_client


@dataclass(slots=True)
class IngestProcessingResult:
    chunks_created: int
    storage_metadata: dict[str, Any]


async def process_ingest_job(
    document_id: str,
    user_id: str,
    file_data: bytes,
    filename: str,
    repo: SupabaseRepo,
    content_type: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> IngestProcessingResult:
    metadata = metadata or {}

    storage_metadata = await cloudinary_storage_client.upload_document(
        user_id=user_id,
        document_id=document_id,
        file_data=file_data,
        filename=filename,
        content_type=content_type,
    )

    try:
        text = extract_text(file_data, content_type=content_type, filename=filename)
        text = clean_text(text)

        chunks = sliding_window_chunks(text)

        all_embeddings = []
        for batch in batched(chunks):
            embeddings = await gemini_client.embed_documents(batch)
            all_embeddings.extend(embeddings)

        chunk_records = []
        for idx, (chunk_text, embedding) in enumerate(zip(chunks, all_embeddings)):
            record = ChunkRecord(
                document_id=document_id,
                user_id=user_id,
                chunk_idx=idx,
                content=chunk_text,
                embedding=embedding,
                metadata={
                    "filename": filename,
                    "total_chunks": len(chunks),
                    **metadata,
                },
            )
            chunk_records.append(record)

        await repo.upsert_chunks(chunk_records)
    except Exception:
        with suppress(Exception):
            await cloudinary_storage_client.delete_document_asset(storage_metadata)
        raise

    return IngestProcessingResult(chunks_created=len(chunks), storage_metadata=storage_metadata)
