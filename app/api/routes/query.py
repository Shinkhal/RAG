import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.redis_cache import redis_cache
from app.config.env_config import get_settings
from app.db import get_session
from app.repositories.supabase_repo import SupabaseRepo
from app.schemas.query import ExternalSearchResult, QueryMetadata, QueryRequest, QueryResponse
from app.services.external_knowledge import get_external_knowledge
from app.services.generation import generate_answer
from app.services.personas import build_persona_prompt_config
from app.services.retrieval import retrieve_chunks

router = APIRouter()

FALLBACK_TOPIC_THRESHOLD = 0.1


@router.post("/query", response_model=QueryResponse)
async def query_rag(
    request: QueryRequest,
    session: AsyncSession = Depends(get_session),
) -> QueryResponse:
    start_time = time.time()
    settings = get_settings()
    repo = SupabaseRepo(session)

    cached = await redis_cache.get_cached_query(
        request.user_id,
        request.query,
        request.persona.persona_id if request.persona else None,
    )
    if cached:
        cached["cached"] = True
        return QueryResponse(**cached)

    top_k = (
        request.config.get("top_k", settings.default_top_k)
        if request.config
        else settings.default_top_k
    )
    min_score = (
        request.config.get("min_score", settings.min_retrieval_score)
        if request.config
        else settings.min_retrieval_score
    )
    document_ids = request.filters.get("doc_ids") if request.filters else None

    chunks_result = await retrieve_chunks(
        query=request.query,
        user_id=request.user_id,
        session_id=request.session_id,
        repo=repo,
        top_k=top_k,
        min_score=min_score,
        document_ids=document_ids,
    )
    chunks_with_scores = chunks_result.chunks
    force_general = chunks_result.low_confidence
    top_score = chunks_with_scores[0][1] if chunks_with_scores else None
    confidence = top_score

    external_results: list[ExternalSearchResult] = []
    if request.enable_external_knowledge:
        context_chunks = [
            {"doc_name": chunk[0]["metadata"].get("filename", "")} for chunk in chunks_with_scores
        ]
        external_results, _ = await get_external_knowledge(request.query, context_chunks)

    persona_payload = None
    if request.persona:
        persona = await repo.get_persona(request.persona.persona_id, include_inactive=False)
        if not persona:
            raise HTTPException(
                status_code=404, detail=f"Persona '{request.persona.persona_id}' not found"
            )
        persona_payload = build_persona_prompt_config(persona, request.persona.intensity)

    answer, sources, llm_details, _ = await generate_answer(
        query=request.query,
        chunks=chunks_with_scores,
        subscription_tier=request.subscription_tier,
        persona_config=persona_payload,
        stream=False,
        force_general=force_general,
        external_results=external_results,
    )

    processing_time_ms = int((time.time() - start_time) * 1000)

    metadata = QueryMetadata(
        persona_applied=request.persona.persona_id if request.persona else None,
        persona_intensity=request.persona.intensity if request.persona else None,
        llm_used=llm_details["model"],
        subscription_tier=request.subscription_tier,
        tokens_used=len(answer.split()),
        processing_time_ms=processing_time_ms,
        cached=False,
        confidence=confidence,
        general_fallback=force_general,
    )

    response = QueryResponse(
        answer=answer,
        sources=sources,
        metadata=metadata,
        external_results=external_results,
    )

    await redis_cache.cache_query_result(
        request.user_id,
        request.query,
        request.persona.persona_id if request.persona else None,
        response.model_dump(),
    )

    await repo.log_query(
        user_id=request.user_id,
        query=request.query,
        answer=answer,
        sources={"sources": [s.model_dump() for s in sources]},
        persona_id=request.persona.persona_id if request.persona else None,
        llm_provider=llm_details["provider"],
        tokens_used=metadata.tokens_used,
        latency_ms=processing_time_ms,
        cached=False,
    )

    return response


@router.post("/query/stream")
async def query_rag_stream(
    request: QueryRequest,
    session: AsyncSession = Depends(get_session),
):
    settings = get_settings()
    repo = SupabaseRepo(session)

    persona_payload = None
    if request.persona:
        persona = await repo.get_persona(request.persona.persona_id, include_inactive=False)
        if not persona:
            raise HTTPException(
                status_code=404, detail=f"Persona '{request.persona.persona_id}' not found"
            )
        persona_payload = build_persona_prompt_config(persona, request.persona.intensity)

    top_k = (
        request.config.get("top_k", settings.default_top_k)
        if request.config
        else settings.default_top_k
    )
    min_score = (
        request.config.get("min_score", settings.min_retrieval_score)
        if request.config
        else settings.min_retrieval_score
    )
    document_ids = request.filters.get("doc_ids") if request.filters else None

    chunks_result = await retrieve_chunks(
        query=request.query,
        user_id=request.user_id,
        session_id=request.session_id,
        repo=repo,
        top_k=top_k,
        min_score=min_score,
        document_ids=document_ids,
    )
    chunks_with_scores = chunks_result.chunks
    force_general = chunks_result.low_confidence
    top_score = chunks_with_scores[0][1] if chunks_with_scores else None
    confidence = top_score

    external_results: list[ExternalSearchResult] = []
    if request.enable_external_knowledge:
        context_chunks = [
            {"doc_name": chunk[0]["metadata"].get("filename", "")} for chunk in chunks_with_scores
        ]
        external_results, _ = await get_external_knowledge(request.query, context_chunks)

    async def event_stream():
        import json

        yield f"data: {json.dumps({'type': 'status', 'message': 'Retrieving context...'})}\n\n"
        yield f"data: {json.dumps({'type': 'retrieval', 'chunks_found': len(chunks_with_scores)})}\n\n"
        if external_results:
            yield f"data: {json.dumps({'type': 'external_search', 'results_count': len(external_results)})}\n\n"
        yield f"data: {json.dumps({'type': 'generation_start'})}\n\n"

        answer, sources, llm_details, _ = await generate_answer(
            query=request.query,
            chunks=chunks_with_scores,
            subscription_tier=request.subscription_tier,
            persona_config=persona_payload,
            stream=True,
            force_general=force_general,
            external_results=external_results,
        )

        async for token in answer:
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        yield f"data: {json.dumps({'type': 'sources', 'sources': [s.model_dump() for s in sources]})}\n\n"
        if external_results:
            yield f"data: {json.dumps({'type': 'external_results', 'results': [r.model_dump() for r in external_results]})}\n\n"
        yield f"data: {json.dumps({'type': 'metadata', 'data': {'llm_used': llm_details['model'], 'subscription_tier': request.subscription_tier, 'persona_applied': request.persona.persona_id if request.persona else None, 'persona_intensity': request.persona.intensity if request.persona else None, 'cached': False, 'confidence': confidence, 'general_fallback': force_general}})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
