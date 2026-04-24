from typing import Any
from app.db.models import Document, IngestJob, QueryLog


class InMemoryRepo:
    def __init__(self):
        self._documents: dict[str, Document] = {}
        self._chunks: dict[str, list[dict[str, Any]]] = {}
        self._jobs: dict[str, IngestJob] = {}
        self._query_logs: list[QueryLog] = []

    async def upsert_document(self, doc: Document) -> Document:
        self._documents[doc.id] = doc
        return doc

    async def upsert_chunks(self, chunks: list[dict[str, Any]]) -> int:
        for chunk in chunks:
            doc_id = chunk["document_id"]
            if doc_id not in self._chunks:
                self._chunks[doc_id] = []
            self._chunks[doc_id].append(chunk)
        return len(chunks)

    async def similarity_search(
        self,
        embedding: list[float],
        user_id: str,
        top_k: int = 20,
        min_score: float = 0.7,
        document_ids: list[str] | None = None,
    ) -> list[tuple[dict[str, Any], float]]:
        results = []
        for doc_id, chunks in self._chunks.items():
            if document_ids and doc_id not in document_ids:
                continue
            for chunk in chunks:
                if chunk["user_id"] == user_id:
                    results.append((chunk, 0.85))
        return results[:top_k]

    async def get_document(self, document_id: str, user_id: str) -> Document | None:
        doc = self._documents.get(document_id)
        if doc and doc.user_id == user_id:
            return doc
        return None

    async def delete_document(self, document_id: str, user_id: str) -> bool:
        doc = self._documents.get(document_id)
        if doc and doc.user_id == user_id:
            del self._documents[document_id]
            if document_id in self._chunks:
                del self._chunks[document_id]
            return True
        return False

    async def create_ingest_job(self, job: IngestJob) -> IngestJob:
        self._jobs[job.job_id] = job
        return job

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        chunks_created: int | None = None,
        error: str | None = None,
    ) -> IngestJob | None:
        job = self._jobs.get(job_id)
        if job:
            job.status = status
            if chunks_created is not None:
                job.chunks_created = chunks_created
            if error is not None:
                job.error = error
            return job
        return None

    async def log_query(
        self,
        user_id: str,
        query: str,
        answer: str,
        sources: dict[str, Any],
        persona_id: str | None = None,
        llm_provider: str | None = None,
        tokens_used: int | None = None,
        latency_ms: int | None = None,
        cached: bool = False,
    ) -> QueryLog:
        log = QueryLog(
            user_id=user_id,
            query=query,
            answer=answer,
            sources=sources,
            persona_id=persona_id,
            llm_provider=llm_provider,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            cached=cached,
        )
        self._query_logs.append(log)
        return log