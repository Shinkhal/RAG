from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.redis_cache import redis_cache
from app.db import get_session
from app.db.models import Persona
from app.repositories.supabase_repo import SupabaseRepo
from app.schemas.persona import PersonaCreateRequest, PersonaResponse, PersonaUpdateRequest
from app.utils.logger import logger

router = APIRouter()


def _to_response(persona: Persona) -> PersonaResponse:
    return PersonaResponse(
        persona_id=persona.persona_id,
        name=persona.name,
        description=persona.description,
        style_config=persona.style_config,
        intensity=persona.intensity,
        sample_responses=persona.sample_responses,
        is_active=persona.is_active,
        is_system=persona.is_system,
        created_by=persona.created_by,
        version=persona.version,
        created_at=persona.created_at,
        updated_at=persona.updated_at,
    )


@router.get("/personas", response_model=list[PersonaResponse])
async def list_personas(session: AsyncSession = Depends(get_session)) -> list[PersonaResponse]:
    # ── cache-aside: try Redis first ──
    cached = await redis_cache.get_cached_persona_list(include_inactive=False)
    if cached is not None:
        logger.debug("Persona list served from cache")
        return [PersonaResponse(**p) for p in cached]

    repo = SupabaseRepo(session)
    personas = await repo.list_personas(include_inactive=False)
    response = [_to_response(persona) for persona in personas]

    # populate cache
    await redis_cache.cache_persona_list(
        [p.model_dump(mode="json") for p in response], include_inactive=False
    )
    return response


@router.get("/personas/{persona_id}", response_model=PersonaResponse)
async def get_persona(
    persona_id: str, session: AsyncSession = Depends(get_session)
) -> PersonaResponse:
    # ── cache-aside: try Redis first ──
    cached = await redis_cache.get_cached_persona(persona_id)
    if cached is not None:
        logger.debug("Persona '%s' served from cache", persona_id)
        return PersonaResponse(**cached)

    repo = SupabaseRepo(session)
    persona = await repo.get_persona(persona_id, include_inactive=False)
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

    response = _to_response(persona)
    await redis_cache.cache_persona(persona_id, response.model_dump(mode="json"))
    return response


@router.post("/admin/personas", response_model=PersonaResponse, status_code=status.HTTP_201_CREATED)
async def create_persona(
    request: PersonaCreateRequest,
    x_admin_id: str | None = Header(default="admin"),
    session: AsyncSession = Depends(get_session),
) -> PersonaResponse:
    repo = SupabaseRepo(session)
    existing = await repo.get_persona(request.persona_id, include_inactive=True)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Persona ID already exists"
        )

    persona = Persona(
        persona_id=request.persona_id,
        name=request.name,
        description=request.description,
        style_config=request.style_config.model_dump(),
        intensity=request.intensity,
        sample_responses=request.sample_responses,
        is_active=request.is_active,
        is_system=False,
        created_by=x_admin_id,
        version=request.version,
    )
    created = await repo.create_persona(persona)

    # invalidate cached lists so the new persona shows up
    await redis_cache.invalidate_all_personas()
    return _to_response(created)


@router.put("/admin/personas/{persona_id}", response_model=PersonaResponse)
async def update_persona(
    persona_id: str,
    request: PersonaUpdateRequest,
    session: AsyncSession = Depends(get_session),
) -> PersonaResponse:
    repo = SupabaseRepo(session)
    updated = await repo.update_persona(
        persona_id,
        name=request.name,
        description=request.description,
        style_config=request.style_config.model_dump() if request.style_config else None,
        intensity=request.intensity,
        sample_responses=request.sample_responses,
        is_active=request.is_active,
        version=request.version,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

    # invalidate stale individual + list caches
    await redis_cache.delete_cached_persona(persona_id)
    await redis_cache.invalidate_all_personas()
    return _to_response(updated)


@router.delete("/admin/personas/{persona_id}")
async def delete_persona(
    persona_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, bool]:
    repo = SupabaseRepo(session)
    deleted = await repo.delete_persona(persona_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Persona not found")

    # purge from cache
    await redis_cache.delete_cached_persona(persona_id)
    await redis_cache.invalidate_all_personas()
    return {"deleted": True}
