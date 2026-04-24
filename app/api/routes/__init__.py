from .bulk import router as bulk_router
from .ingest import router as ingest_router
from .persona import router as persona_router
from .query import router as query_router

__all__ = ["ingest_router", "query_router", "bulk_router", "persona_router"]
