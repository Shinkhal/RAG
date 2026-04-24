"""
Central registry for all Redis cache keys.

Every Redis key used across the service MUST be defined here so naming
conventions stay consistent and stale-key bugs are easy to track down.
"""


class RedisKeys:
    """Namespace container for all Redis key patterns."""

    # ── Query Cache ──────────────────────────────────────────────────
    # Key: query_cache:{user_id}:{hash}   TTL: configurable
    QUERY_CACHE_PREFIX = "query_cache"

    @staticmethod
    def query_cache(user_id: str, query_hash: str) -> str:
        return f"{RedisKeys.QUERY_CACHE_PREFIX}:{user_id}:{query_hash}"

    # ── Persona Cache ────────────────────────────────────────────────
    # Single persona  → persona:{persona_id}
    # Full list       → persona:list:active  /  persona:list:all
    PERSONA_PREFIX = "persona"
    PERSONA_LIST_ACTIVE = "persona:list:active"
    PERSONA_LIST_ALL = "persona:list:all"
    PERSONA_TTL_SECONDS = 600  # 10 minutes

    @staticmethod
    def persona(persona_id: str) -> str:
        return f"{RedisKeys.PERSONA_PREFIX}:{persona_id}"

    # ── Ingest Jobs ──────────────────────────────────────────────────
    INGEST_JOB_PREFIX = "ingest_job"

    @staticmethod
    def ingest_job(job_id: str) -> str:
        return f"{RedisKeys.INGEST_JOB_PREFIX}:{job_id}"

    # ── Documents ────────────────────────────────────────────────────
    DOCUMENT_PREFIX = "document"

    @staticmethod
    def document(document_id: str) -> str:
        return f"{RedisKeys.DOCUMENT_PREFIX}:{document_id}"
