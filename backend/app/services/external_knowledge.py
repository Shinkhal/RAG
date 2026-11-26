import logging
from typing import Any

from app.config.env_config import get_settings
from app.schemas.query import ExternalSearchResult

logger = logging.getLogger("app.external_knowledge")


async def search_web(query: str, num_results: int = 5) -> list[ExternalSearchResult]:
    settings = get_settings()

    if not settings.tavily_api_key:
        logger.warning("External knowledge skipped: TAVILY_API_KEY is not configured.")
        return []

    try:
        from tavily import AsyncTavilyClient

        client = AsyncTavilyClient(api_key=settings.tavily_api_key)
        response = await client.search(query=query, max_results=num_results)

        results = []
        for result in response.get("results", []):
            results.append(
                ExternalSearchResult(
                    title=result.get("title", ""),
                    url=result.get("url", ""),
                    snippet=result.get("content", ""),
                )
            )

        return results

    except Exception:
        logger.exception("External knowledge search failed for query=%r", query)
        return []


async def get_external_knowledge(
    query: str,
    context_chunks: list[dict[str, Any]],
    num_results: int = 3,
) -> tuple[list[ExternalSearchResult], str | None]:
    if not context_chunks:
        search_results = await search_web(query, num_results)
    else:
        unique_docs = set(chunk.get('doc_name', '') for chunk in context_chunks if chunk.get('doc_name', '').strip())
        doc_context = " ".join(unique_docs)
        combined_query = f"{query} {doc_context}".strip()
        search_results = await search_web(combined_query, num_results)

    if not search_results:
        return [], None

    summary_parts = []
    for i, result in enumerate(search_results, 1):
        summary_parts.append(f"{i}. {result.title}\n   {result.snippet}")

    summary = "\n".join(summary_parts)
    return search_results, summary
