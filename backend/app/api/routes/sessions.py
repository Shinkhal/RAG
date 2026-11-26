import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import current_user_id
from app.db import get_session as get_db_session
from app.db.models import ChatSession, ConversationTurn, Document
from app.repositories.supabase_repo import SupabaseRepo
from app.schemas.query import QueryResponse

router = APIRouter()


class SessionResponse(BaseModel):
    id: str
    user_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime


class CreateSessionRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)


class SessionDocument(BaseModel):
    id: str
    name: str
    status: str
    chunks_created: int


class HistoryTurn(BaseModel):
    question: str
    response: QueryResponse


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    user_id: str = Depends(current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    repo = SupabaseRepo(db_session)
    session_id = str(uuid.uuid4())

    chat_session = ChatSession(
        id=session_id,
        user_id=user_id,
        title=request.title,
    )
    created = await repo.create_session(chat_session)

    return SessionResponse(
        id=created.id,
        user_id=created.user_id,
        title=created.title,
        created_at=created.created_at,
        updated_at=created.updated_at,
    )


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    user_id: str = Depends(current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
) -> list[SessionResponse]:
    repo = SupabaseRepo(db_session)
    sessions = await repo.list_sessions(user_id)

    return [
        SessionResponse(
            id=s.id,
            user_id=s.user_id,
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    user_id: str = Depends(current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    repo = SupabaseRepo(db_session)
    session = await repo.get_session(session_id, user_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user_id: str = Depends(current_user_id),
    db_session: AsyncSession = Depends(get_db_session),
) -> dict[str, bool]:
    repo = SupabaseRepo(db_session)
    deleted = await repo.delete_session(session_id, user_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"deleted": True}


@router.get("/sessions/{session_id}/documents")
async def list_session_documents(
    session_id: str,
    user_id: str = Depends(current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> list[SessionDocument]:
    if not await SupabaseRepo(db).get_session(session_id, user_id):
        raise HTTPException(404, "Session not found")
    documents = await db.scalars(
        select(Document)
        .where(Document.session_id == session_id, Document.user_id == user_id)
        .order_by(Document.created_at.desc())
    )
    return [
        SessionDocument(
            id=doc.id,
            name=doc.metadata_.get("uploaded_filename") or doc.id,
            status=doc.status,
            chunks_created=doc.chunks_created,
        )
        for doc in documents
    ]


@router.get("/sessions/{session_id}/history")
async def get_history(
    session_id: str,
    user_id: str = Depends(current_user_id),
    db: AsyncSession = Depends(get_db_session),
) -> list[HistoryTurn]:
    if not await SupabaseRepo(db).get_session(session_id, user_id):
        raise HTTPException(404, "Session not found")
    turns = await db.scalars(
        select(ConversationTurn)
        .where(ConversationTurn.session_id == session_id)
        .order_by(ConversationTurn.id.desc())
        .limit(100)
    )
    return [
        HistoryTurn(question=turn.question, response=turn.response)
        for turn in reversed(turns.all())
    ]
