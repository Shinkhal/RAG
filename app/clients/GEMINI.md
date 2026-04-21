# Gemini Embeddings & LLM Client

**File:** `app/clients/gemini.py`

## Responsibilities
- Generate embeddings for documents (RETRIEVAL_DOCUMENT task) 
- Generate embeddings for queries (RETRIEVAL_QUERY task)
- Call Gemini Flash / Pro models for generation
- Handle batching for efficiency (up to 128 chunks/call)

## Key Methods
```
embed_documents(texts: list[str]) -> list[list[float]]
embed_query(query: str) -> list[float]
generate(prompt: str, model: str, temperature: float) -> str
generate_stream(prompt: str, model: str) -> AsyncIterator[str]
```

## Notes
- Dimension: 768
- Free tier: 1,500 req/min
- Batch documents, query separately
