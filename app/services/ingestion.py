from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from app.clients.cloudinary_storage import cloudinary_storage_client
from app.clients.gemini import gemini_client
from app.repositories.supabase_repo import ChunkRecord, SupabaseRepo
from app.services.chunking import (
    ExtractedPage,
    batched,
    extract_pages_from_pdf,
    extract_text,
    is_informative_text,
    make_text_splitter,
    normalize_document_text,
    sliding_window_chunks,
)


@dataclass(slots=True)
class IngestProcessingResult:
    chunks_created: int
    storage_metadata: dict[str, Any]


def _chunk_pages(
    pages: list[ExtractedPage], chunk_size: int | None, overlap: int | None
) -> list[tuple[int, str]]:
    splitter = make_text_splitter(chunk_size, overlap)

    all_chunks: list[tuple[int, str]] = []
    for page in pages:
        page_chunks = splitter.split_text(page.text)
        for chunk_text in page_chunks:
            if is_informative_text(chunk_text):
                all_chunks.append((page.page_num, chunk_text))

    return all_chunks


async def process_ingest_job(
    document_id: str,
    session_id: str,
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
        if content_type == "application/pdf" or (
            filename and filename.rsplit(".", 1)[-1].lower() == "pdf"
        ):
            pages = extract_pages_from_pdf(file_data)
            page_chunked = _chunk_pages(pages, chunk_size=None, overlap=None)
            total_chunks = len(page_chunked)
            if not page_chunked:
                raise ValueError("No indexable text was found in the PDF.")

            all_embeddings = []
            texts = [c[1] for c in page_chunked]
            for batch_texts in batched(texts):
                embeddings = await gemini_client.embed_documents(batch_texts)
                all_embeddings.extend(embeddings)

            if len(all_embeddings) != len(page_chunked):
                raise ValueError(
                    f"Embedding count mismatch for PDF ingestion: expected {len(page_chunked)} got {len(all_embeddings)}"
                )

            chunk_records = []
            for idx, ((page_num, chunk_text), embedding) in enumerate(
                zip(page_chunked, all_embeddings)
            ):
                record = ChunkRecord(
                    document_id=document_id,
                    session_id=session_id,
                    user_id=user_id,
                    chunk_idx=idx,
                    content=chunk_text,
                    embedding=embedding,
                    metadata={
                        "filename": filename,
                        "total_chunks": total_chunks,
                        "chunk_id": idx,
                        "page": page_num,
                        **metadata,
                    },
                )
                chunk_records.append(record)
        else:
            raw_text = extract_text(file_data, content_type=content_type, filename=filename)
            text = normalize_document_text(raw_text)
            chunks = [
                chunk
                for chunk in sliding_window_chunks(text)
                if is_informative_text(chunk)
            ]
            total_chunks = len(chunks)
            if not chunks:
                raise ValueError("No indexable text was found in the document.")

            all_embeddings = []
            for batch in batched(chunks):
                embeddings = await gemini_client.embed_documents(batch)
                all_embeddings.extend(embeddings)

            if len(all_embeddings) != len(chunks):
                raise ValueError(
                    f"Embedding count mismatch for text ingestion: expected {len(chunks)} got {len(all_embeddings)}"
                )

            chunk_records = []
            for idx, (chunk_text, embedding) in enumerate(zip(chunks, all_embeddings)):
                record = ChunkRecord(
                    document_id=document_id,
                    session_id=session_id,
                    user_id=user_id,
                    chunk_idx=idx,
                    content=chunk_text,
                    embedding=embedding,
                    metadata={
                        "filename": filename,
                        "total_chunks": total_chunks,
                        "chunk_id": idx,
                        "page": None,
                        **metadata,
                    },
                )
                chunk_records.append(record)

        await repo.upsert_chunks(chunk_records)

        # Build and cache document context for summarization
        from app.clients.redis_cache import redis_cache

        # Build full text from chunks
        full_text = "\n\n".join(c.content for c in chunk_records)

        # Build page mapping if available
        pages = []
        if chunk_records and "page" in chunk_records[0].metadata:
            pages = [
                {"page": c.metadata.get("page"), "chunk_idx": i}
                for i, c in enumerate(chunk_records)
                if c.metadata.get("page")
            ]

        context = {
            "document_id": document_id,
            "filename": filename,
            "full_text": full_text,
            "chunk_count": len(chunk_records),
            "pages": pages,
            "created_at": __import__("datetime").datetime.utcnow().isoformat(),
        }

        await redis_cache.set_document_context(document_id, context)
    except Exception:
        with suppress(Exception):
            await cloudinary_storage_client.delete_document_asset(storage_metadata)
        raise

    return IngestProcessingResult(
        chunks_created=len(chunk_records), storage_metadata=storage_metadata
    )
