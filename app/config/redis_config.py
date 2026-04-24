from typing import Optional

import requests

from app.config.env_config import GetEnv
from app.utils.logger import logger


class RedisConnection:
    _instance: Optional["RedisConnection"] = None

    def __init__(self):
        logger.info("Initializing Upstash Redis client")

        self.url = GetEnv.redis.url()
        self.token = GetEnv.redis.token()

        if not self.url or not self.token:
            raise ValueError(
                "Missing Redis configuration: set UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN"
            )

        logger.info("Upstash Redis client initialized")

    @classmethod
    def get_instance(cls) -> "RedisConnection":
        if cls._instance is None:
            cls._instance = RedisConnection()
        return cls._instance

    # ----------------------------------
    # Internal HTTP request helper
    # ----------------------------------
    def _request(self, command: str, *args):
        try:
            endpoint = f"{self.url}/{command}/" + "/".join(map(str, args))

            headers = {"Authorization": f"Bearer {self.token}"}

            response = requests.get(endpoint, headers=headers)

            if response.status_code != 200:
                raise Exception(f"Redis error: {response.text}")

            return response.json()

        except Exception as e:
            logger.error(f"Redis request failed: {e}")
            raise

    # ----------------------------------
    # Public Redis-like APIs
    # ----------------------------------

    def get(self, key: str):
        return self._request("get", key)

    def set(self, key: str, value: str):
        return self._request("set", key, value)

    def incr(self, key: str):
        return self._request("incr", key)

    def expire(self, key: str, seconds: int):
        return self._request("expire", key, seconds)

    def ping(self):
        return self._request("ping")

    # ----------------------------------
    # Lifecycle
    # ----------------------------------

    async def connect(self):
        try:
            res = self.ping()
            logger.info(f"Redis connected: {res}")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            raise

    async def health_check(self) -> bool:
        try:
            self.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    async def disconnect(self):
        logger.debug("Closing Redis connections (no-op for HTTP Redis)")


# ----------------------------------
# Lazy accessor (same as TS)
# ----------------------------------


def get_redis_client() -> RedisConnection:
    return RedisConnection.get_instance()
