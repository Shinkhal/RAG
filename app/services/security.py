import re
from typing import Any


BANNED_PATTERNS = [
    r"ignore (previous|above|all)",
    r"you are now",
    r"system:",
    r"<\|.*?\|>",
    r"disregard",
    r"forget (everything|all|previous)",
]


def sanitize_context(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized = []
    for chunk in chunks:
        text = chunk.get("content", "")
        for pattern in BANNED_PATTERNS:
            text = re.sub(pattern, "[FILTERED]", text, flags=re.IGNORECASE)
        sanitized.append({**chunk, "content": text})
    return sanitized


def validate_persona_response(original: str, personafied: str) -> str:
    original_facts = set(extract_facts(original))
    persona_facts = set(extract_facts(personafied))

    missing_facts = original_facts - persona_facts
    if missing_facts and len(missing_facts) > len(original_facts) * 0.2:
        return original

    return personafied


def extract_facts(text: str) -> list[str]:
    sentences = re.split(r"[.!?]+", text)
    facts = [s.strip().lower() for s in sentences if len(s.strip()) > 10]
    return facts


def rate_limit_key(user_id: str, tier: str) -> str:
    return f"rate_limit:{tier}:{user_id}"


RATE_LIMITS = {
    "free": 50,
    "pro": 500,
    "enterprise": -1,
}