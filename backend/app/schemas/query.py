from typing import Any

from pydantic import BaseModel, Field


class ExternalSearchResult(BaseModel):
    title: str
    url: str
    snippet: str


class SourceReference(BaseModel):
    doc_id: str
    doc_name: str | None = None
    page: int | None = None
    excerpt: str | None = None
    relevance: float | None = None


class PersonaConfig(BaseModel):
    persona_id: str
    intensity: float = Field(default=0.8, ge=0.0, le=1.0)


class QueryInput(BaseModel):
    query: str = Field(min_length=1, max_length=8000)
    session_id: str
    persona: PersonaConfig | None = None
    filters: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    enable_external_knowledge: bool = Field(default=False, description="Enable internet search to supplement document context")


class QueryRequest(QueryInput):
    user_id: str
    subscription_tier: str = "free"


class QueryMetadata(BaseModel):
    persona_applied: str | None = None
    persona_intensity: float | None = None
    llm_used: str
    subscription_tier: str
    tokens_used: int
    processing_time_ms: int
    cached: bool = False
    confidence: float | None = None
    general_fallback: bool = False


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceReference]
    metadata: QueryMetadata
    external_results: list[ExternalSearchResult] = Field(default_factory=list, description="Web search results if external knowledge is enabled")


class StreamingToken(BaseModel):
    type: str = "token"
    content: str


class StreamingSource(BaseModel):
    type: str = "sources"
    sources: list[SourceReference]


class StreamingMetadata(BaseModel):
    type: str = "metadata"
    data: QueryMetadata


class StreamingDone(BaseModel):
    type: str = "done"


class ExternalKnowledgeContext(BaseModel):
    has_external_context: bool = False
    results: list[ExternalSearchResult] = Field(default_factory=list)
    summary: str | None = None
