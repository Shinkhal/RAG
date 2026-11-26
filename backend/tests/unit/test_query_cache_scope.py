from app.clients.redis_cache import RedisCache


def test_query_cache_key_includes_session_and_request_options() -> None:
    cache = RedisCache.__new__(RedisCache)

    first_session = cache._make_key(
        "student-1", "What is mitosis?", session_id="session-1"
    )
    second_session = cache._make_key(
        "student-1", "What is mitosis?", session_id="session-2"
    )
    filtered_query = cache._make_key(
        "student-1",
        "What is mitosis?",
        session_id="session-1",
        options={"filters": {"doc_ids": ["doc-1"]}},
    )

    assert first_session != second_session
    assert first_session != filtered_query
