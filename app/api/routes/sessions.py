import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.db.models import ChatSession
from app.repositories.supabase_repo import SupabaseRepo

router = APIRouter()


class SessionResponse(BaseModel):
    id: str
    user_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime


class CreateSessionRequest(BaseModel):
    user_id: str
    title: str | None = None


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    db_session: AsyncSession = Depends(get_session),
) -> SessionResponse:
    repo = SupabaseRepo(db_session)
    session_id = str(uuid.uuid4())

    chat_session = ChatSession(
        id=session_id,
        user_id=request.user_id,
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


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    user_id: str,
    db_session: AsyncSession = Depends(get_session),
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
    user_id: str,
    db_session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    repo = SupabaseRepo(db_session)
    deleted = await repo.delete_session(session_id, user_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")

    return {"deleted": True}


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    user_id: str,
    db_session: AsyncSession = Depends(get_session),
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
