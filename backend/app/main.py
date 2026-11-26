import asyncio
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware import Middleware

from app.api.router import api_router
from app.clients.redis_cache import redis_cache
from app.config.cloudinary_config import CloudinaryConfig
from app.config.env_config import get_env, get_settings
from app.core.middleware import RequestLoggingMiddleware
from app.db import init_db
from app.middleware.rate_limit import RateLimitMiddleware
from app.services.personas import ensure_default_personas
from app.utils.logger import logger
from app.workers.queue import consume_ingest_jobs


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.start_time = time.time()
    worker_task = None

    try:
        CloudinaryConfig.initialize()
        if not await CloudinaryConfig.health_check():
            if get_settings().app_env == "production":
                raise Exception("Cloudinary health check failed during startup")
            logger.warning("Cloudinary health check failed during startup")

        if not await redis_cache.health_check():
            if get_settings().is_production:
                raise RuntimeError("Redis health check failed during startup")
            logger.warning("Redis health check failed during startup")

        await init_db()
        app.state.db_ready = True

        # Persona seeding is optional; a failure here must not prevent the
        # ingestion worker from starting, or uploads would queue forever.
        try:
            await ensure_default_personas()
        except Exception:
            logger.exception("Failed to seed default personas; continuing startup")

        worker_task = asyncio.create_task(consume_ingest_jobs())

    except Exception as exc:
        app.state.db_ready = False
        if get_settings().app_env == "production":
            raise

        logger.warning(
            "Service initialization skipped during startup in %s mode: %s",
            get_settings().app_env,
            exc,
        )
        # Start the worker even when initialization was incomplete. If the
        # database recovers, queued uploads will be processed instead of being
        # stranded in the queue with no worker watching them.
        worker_task = asyncio.create_task(consume_ingest_jobs())

    try:
        yield
    finally:
        if worker_task:
            worker_task.cancel()
            with suppress(asyncio.CancelledError):
                await worker_task
        await redis_cache.close()


app = FastAPI(
    title="RAG Microservice",
    description="NotebookLM-style RAG with persona-based responses",
    version="1.0",
    lifespan=lifespan,
    middleware=[
        Middleware(
            RateLimitMiddleware,
            exclude_paths=[
                "/",
                "/health",
                "/workspace",
                "/profile",
                "/login",
                "/signup",
                "/forgot-password",
                "/reset-password",
            ],
        ),
        Middleware(RequestLoggingMiddleware),
    ],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check() -> dict[str, Any]:
    # Check database status
    db_ready = getattr(app.state, "db_ready", False)

    # Check Cloudinary health asynchronously
    cloudinary_healthy = await CloudinaryConfig.health_check()

    # Check Redis health
    redis_healthy = await redis_cache.health_check()

    # Overall status: healthy if all services are ready
    overall_status = (
        "healthy" if (db_ready and cloudinary_healthy and redis_healthy) else "degraded"
    )

    return {
        "status": overall_status,
        "database": "ready" if db_ready else "not_ready",
        "cloudinary": "healthy" if cloudinary_healthy else "not_healthy",
        "redis": "connected" if redis_healthy else "not_connected",
        "latency_ms": int((time.time() - getattr(app.state, "start_time", time.time())) * 1000),
        "env": get_env().app.env(),
    }


def format_uptime(seconds: int):
    mins, sec = divmod(seconds, 60)
    hrs, mins = divmod(mins, 60)
    return f"{hrs}h {mins}m {sec}s"


web_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
app.mount(
    "/assets", StaticFiles(directory=web_dir / "assets", check_dir=False), name="workspace-assets"
)


@app.get("/login", include_in_schema=False)
@app.get("/signup", include_in_schema=False)
@app.get("/workspace", include_in_schema=False)
@app.get("/profile", include_in_schema=False)
@app.get("/forgot-password", include_in_schema=False)
@app.get("/reset-password", include_in_schema=False)
async def workspace():
    index = web_dir / "index.html"
    if not index.is_file():
        return JSONResponse(
            status_code=503,
            content={"detail": "Build the frontend with npm ci and npm run build in frontend/."},
        )
    return FileResponse(
        index,
        headers={
            "Content-Security-Policy": (
                "default-src 'self'; object-src 'none'; base-uri 'none'; "
                "frame-ancestors 'none'; form-action 'self'"
            ),
            "Cache-Control": "no-store",
        },
    )


@app.get("/")
async def root(request: Request):
    if "text/html" in request.headers.get("accept", ""):
        return RedirectResponse("/workspace", headers={"Vary": "Accept"})
    env = get_env()

    start_time = getattr(app.state, "start_time", None)
    uptime_seconds = int(time.time() - start_time) if start_time else 0

    return JSONResponse({
        "message": "Welcome to the RAG Microservice 🚀",
        "status": "running",
        "environment": env.app.env(),
        "uptime": format_uptime(uptime_seconds),
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
        "workspace": "/workspace",
    }, headers={"Vary": "Accept"})
