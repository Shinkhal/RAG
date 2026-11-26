# Generation Service

**File:** `app/services/generation.py`

## Responsibilities
- Route queries to appropriate model
- Synthesize grounded answers from chunks
- Enforce citations
- Detect hallucination

## Key Functions
```
pick_model(
    query: str,
    chunk_scores: list[float]
) -> str
    Returns: "gemini-2.0-flash" | "gemini-2.5-pro"

grounded_answer(
    query: str,
    chunks: list[tuple[text, doc_name, page]]
) -> tuple[answer: str, sources: list[SourceRef]]
```

## Model Routing Logic
- **Gemini Flash** (80%): Simple Q&A (avg_score ≥ 0.75, query < 30 words)
- **Gemini Pro** (20%): Complex synthesis, low confidence retrieval

## Answer Format
```
{
  "answer": "...",
  "sources": [
    {"doc": "policy.pdf", "page": 3},
    ...
  ],
  "model": "gemini-2.0-flash",
  "avg_score": 0.82
}
```

## Guardrails
- Citation enforcement: every response must cite [doc, page]
- Confidence threshold: if avg_score < 0.7, respond "Insufficient information"
- No fabrication: model instructed to admit gaps
- LLM judge (5% sample): validate grounding separately
