from typing import Any, AsyncIterator

from app.llms.router import get_tier_llm_client
from app.schemas.query import SourceReference


async def generate_answer(
    query: str,
    chunks: list[tuple[dict[str, Any], float]],
    subscription_tier: str = "free",
    persona_config: dict[str, Any] | None = None,
    stream: bool = False,
) -> tuple[str | AsyncIterator[str], list[SourceReference], dict[str, str]]:
    llm_client = get_tier_llm_client(subscription_tier)

    context_chunks = [
        {
            "content": chunk["content"],
            "doc_name": chunk["metadata"].get("filename", "Unknown"),
            "page": chunk["metadata"].get("page"),
        }
        for chunk, score in chunks
    ]

    sources = [
        SourceReference(
            doc_id=chunk["doc_id"],
            doc_name=chunk["metadata"].get("filename"),
            page=chunk["metadata"].get("page"),
            excerpt=chunk["content"][:200] + "..." if len(chunk["content"]) > 200 else chunk["content"],
            relevance=score,
        )
        for chunk, score in chunks
    ]

    if stream:
        result = await llm_client.grounded_answer(
            query=query,
            context_chunks=context_chunks,
            persona_config=persona_config,
            stream=True,
        )
        return result, sources, {"provider": llm_client.provider, "model": llm_client.model_name}

    answer = await llm_client.grounded_answer(
        query=query,
        context_chunks=context_chunks,
        persona_config=persona_config,
        stream=False,
    )

    return answer, sources, {"provider": llm_client.provider, "model": llm_client.model_name}
