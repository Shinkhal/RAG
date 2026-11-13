import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware import Middleware

from app.api.router import api_router
from app.config.cloudinary_config import CloudinaryConfig
from app.config.env_config import get_env, get_settings
from app.config.redis_config import RedisConnection
from app.core.middleware import RequestLoggingMiddleware
from app.db import init_db
from app.middleware.rate_limit import RateLimitMiddleware
from app.services.personas import ensure_default_personas
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    app.state.start_time = time.time()

    try:
        CloudinaryConfig.initialize()
        if not await CloudinaryConfig.health_check():
            if get_settings().app_env == "production":
                raise Exception("Cloudinary health check failed during startup")
            logger.warning("Cloudinary health check failed during startup")

        redis_client = RedisConnection.get_instance()
        await redis_client.connect()

        await init_db()
        await ensure_default_personas()

        app.state.db_ready = True

    except Exception as exc:
        app.state.db_ready = False
        if get_settings().app_env == "production":
            raise

        logger.warning(
            "Service initialization skipped during startup in %s mode: %s",
            get_settings().app_env,
            exc,
        )

    yield
    await redis_client.disconnect()
    # TODO: add Cloudinary shutdown if needed


app = FastAPI(
    title="RAG Microservice",
    description="NotebookLM-style RAG with persona-based responses",
    version="1.0",
    lifespan=lifespan,
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        Middleware(
            RateLimitMiddleware,
            exclude_paths=["/api/v1/ingest"],
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
    redis_client = RedisConnection.get_instance()
    redis_healthy = await redis_client.health_check()

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


@app.get("/")
async def root():
    settings = get_settings()
    env = get_env()

    start_time = getattr(app.state, "start_time", None)
    uptime_seconds = int(time.time() - start_time) if start_time else 0

    return {
        "message": "Welcome to the RAG Microservice 🚀",
        "status": "running",
        "environment": env.app.env(),
        "uptime": format_uptime(uptime_seconds),
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
