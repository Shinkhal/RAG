# Testing Strategy

## Unit Tests (`tests/unit/`)

### test_chunking.py
- Sliding window edge cases (empty text, single word, tables)
- Batch function correctness
- Token count validation

### test_sanitizer.py
- Banned pattern coverage (ignore, new instruction, system:)
- False positive check (legitimate text not redacted)

### test_retrieval.py
- Cosine similarity correctness
- Score threshold filtering
- User_id namespace isolation

### test_generation.py
- Model routing logic (Flash vs Pro)
- Answer synthesis with citations
- Hallucination prevention checks

---

## Integration Tests (`tests/integration/`)

### test_ingest_e2e.py
- Upload doc → ingest → verify chunks stored
- Status polling works
- Retry on failure

### test_query_e2e.py
- Ingest doc → query → get grounded answer
- Streaming SSE response
- Cache hit/miss behavior

### test_multiuser.py
- User A docs not visible to User B
- Namespace isolation verified
- Row-level security enforced

---

## Load Tests (`ops/k6-load-test.js`)
- 1,000 concurrent queries
- Assert p95 < 2s latency
- Cache hit rate tracking

---

## Eval (RAG Quality)

- **Retrieval:** MRR@5 > 0.85 on labeled test set
- **Generation:** RAGAS score — faithfulness > 0.9, relevance > 0.85
- **Manual spot checks:** weekly 20-query sample
