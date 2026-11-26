# Security Service

**File:** `app/services/security.py`

## Responsibilities
- Sanitize chunks to prevent prompt injection
- Detect banned patterns (ignore instructions, new instructions, system:)
- Redact malicious content

## Key Functions
```
sanitize_chunk(text: str) -> str
    Redacts: "ignore previous", "new instruction", "system:", "<|...|>"
```

## Patterns to Block
```
r"ignore (previous|above|all)"
r"new instruction"
r"system:"
r"<\|.*?\|>"
```

## Applied At
- Chunk storage (in `app/services/ingestion.py`)
- Query construction (guard against prompt injection in retrieval)
