from fastapi import APIRouter

from app.api.routes import bulk, ingest, persona, query, sessions

api_router = APIRouter()

api_router.include_router(ingest.router, prefix="/rag", tags=["ingest"])
api_router.include_router(query.router, prefix="/rag", tags=["query"])
api_router.include_router(bulk.router, prefix="/rag", tags=["bulk"])
api_router.include_router(persona.router, prefix="/rag", tags=["persona"])
api_router.include_router(sessions.router, prefix="/rag", tags=["sessions"])
