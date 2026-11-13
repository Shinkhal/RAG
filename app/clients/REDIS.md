# Upstash Redis Cache

**File:** `app/clients/redis_cache.py`

## Responsibilities
- Cache query results (key: hash of query + user_id)
- TTL: 1 hour default
- Deduplicate repeated queries

## Key Methods
```
get(key: str) -> object | None
set(key: str, value: object, ttl_seconds: int) -> None
delete(key: str) -> None
```

## Key Format
```
query_cache:{user_id}:{query_hash}
```

## Notes
- Cost: ~$10/mo
- No egress fees
- Replaces ElastiCache ($150/mo)
