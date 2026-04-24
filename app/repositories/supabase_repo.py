import hashlib
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatSession, Chunk, Document, IngestJob, Persona, QueryLog


class ChunkRecord:
    def __init__(
        self,
        document_id: str,
        session_id: str,
        user_id: str,
        chunk_idx: int,
        content: str,
        embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.document_id = document_id
        self.session_id = session_id
        self.user_id = user_id
        self.chunk_idx = chunk_idx
        self.content = content
        self.embedding = embedding
        self.metadata = metadata or {}

    @property
    def chunk_id(self) -> str:
        return hashlib.sha256(f"{self.document_id}_{self.chunk_idx}".encode()).hexdigest()[:16]


class SupabaseRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_document(self, doc: Document) -> Document:
        self.session.add(doc)
        await self.session.commit()
        await self.session.refresh(doc)
        return doc

    async def upsert_chunks(self, chunks: list[ChunkRecord]) -> int:
        for chunk in chunks:
            db_chunk = Chunk(
                document_id=chunk.document_id,
                session_id=chunk.session_id,
                user_id=chunk.user_id,
                chunk_idx=chunk.chunk_idx,
                content=chunk.content,
                embedding=chunk.embedding,
                metadata_=chunk.metadata,
            )
            self.session.add(db_chunk)
        await self.session.commit()
        return len(chunks)

    async def similarity_search(
        self,
        embedding: list[float],
        user_id: str,
        session_id: str,
        top_k: int = 20,
        min_score: float = 0.7,
        document_ids: list[str] | None = None,
    ) -> list[tuple[Chunk, float]]:
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        query = text("""
            SELECT c.*, 1 - (c.embedding <=> CAST(:embedding AS vector)) as score
            FROM chunks c
            WHERE c.user_id = :user_id
            AND c.session_id = :session_id
            AND 1 - (c.embedding <=> CAST(:embedding AS vector)) >= :min_score
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
        """)

        params = {
            "embedding": embedding_str,
            "user_id": user_id,
            "session_id": session_id,
            "min_score": min_score,
            "limit": top_k,
        }

        if document_ids:
            doc_list = ",".join(f"'{d}'" for d in document_ids)
            query = text(f"""
                SELECT c.*, 1 - (c.embedding <=> CAST(:embedding AS vector)) as score
                FROM chunks c
                WHERE c.user_id = :user_id
                AND c.session_id = :session_id
                AND c.document_id IN ({doc_list})
                AND 1 - (c.embedding <=> CAST(:embedding AS vector)) >= :min_score
                ORDER BY c.embedding <=> CAST(:embedding AS vector)
                LIMIT :limit
            """)

        result = await self.session.execute(query, params)
        rows = result.fetchall()

        chunks_with_scores = []
        for row in rows:
            chunk = await self.session.get(Chunk, row.id)
            if chunk:
                chunks_with_scores.append((chunk, row.score))

        return chunks_with_scores

    async def get_document(self, document_id: str, user_id: str) -> Document | None:
        stmt = select(Document).where(Document.id == document_id, Document.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_document(self, document_id: str, user_id: str) -> bool:
        stmt = delete(Document).where(Document.id == document_id, Document.user_id == user_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def create_ingest_job(self, job: IngestJob) -> IngestJob:
        self.session.add(job)
        await self.session.commit()
        await self.session.refresh(job)
        return job

    async def update_job_status(
        self,
        job_id: str,
        status: str,
        chunks_created: int | None = None,
        error: str | None = None,
    ) -> IngestJob | None:
        stmt = select(IngestJob).where(IngestJob.job_id == job_id)
        result = await self.session.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            return None

        job.status = status
        if chunks_created is not None:
            job.chunks_created = chunks_created
        if error is not None:
            job.error = error

        await self.session.commit()
        await self.session.refresh(job)
        return job

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
        self.session.add(log)
        await self.session.commit()
        return log

    async def list_personas(self, include_inactive: bool = False) -> list[Persona]:
        stmt = select(Persona)
        if not include_inactive:
            stmt = stmt.where(Persona.is_active.is_(True))
        stmt = stmt.order_by(Persona.created_at.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_persona(self, persona_id: str, include_inactive: bool = False) -> Persona | None:
        stmt = select(Persona).where(Persona.persona_id == persona_id)
        if not include_inactive:
            stmt = stmt.where(Persona.is_active.is_(True))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_persona(self, persona: Persona) -> Persona:
        self.session.add(persona)
        await self.session.commit()
        await self.session.refresh(persona)
        return persona

    async def update_persona(self, persona_id: str, **updates: Any) -> Persona | None:
        persona = await self.get_persona(persona_id, include_inactive=True)
        if not persona:
            return None

        for key, value in updates.items():
            if value is not None and hasattr(persona, key):
                setattr(persona, key, value)

        await self.session.commit()
        await self.session.refresh(persona)
        return persona

    async def delete_persona(self, persona_id: str) -> bool:
        stmt = delete(Persona).where(Persona.persona_id == persona_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def create_session(self, session: ChatSession) -> ChatSession:
        self.session.add(session)
        await self.session.commit()
        await self.session.refresh(session)
        return session

    async def get_session(self, session_id: str, user_id: str) -> ChatSession | None:
        stmt = select(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == user_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_session(self, session_id: str, user_id: str) -> bool:
        stmt = delete(ChatSession).where(
            ChatSession.id == session_id, ChatSession.user_id == user_id
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def list_sessions(self, user_id: str) -> list[ChatSession]:
        stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == user_id)
            .order_by(ChatSession.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
