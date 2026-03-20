import json
from typing import Any

import redis

from app.core.interfaces import CacheServiceInterface
from app.utils.exceptions import CacheConnectionError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RedisCache(CacheServiceInterface):
    """Redis-based cache implementation."""

    def __init__(self, redis_client: redis.Redis, default_ttl: int = 86400):
        self._redis_client = redis_client
        self.default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        """Get value from cache by key."""
        try:
            value = self._redis_client.get(key)
            if value is None:
                return None
            return json.loads(value)  # type: ignore[arg-type]
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error("cache_get_failed", extra={"key": key, "error": str(e)})
            raise CacheConnectionError(f"Cache get failed: {e}") from e

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache with optional TTL."""
        try:
            ttl = ttl or self.default_ttl
            serialized_value = json.dumps(value)
            self._redis_client.setex(key, ttl, serialized_value)
        except (redis.RedisError, TypeError, ValueError) as e:
            logger.error("cache_set_failed", extra={"key": key, "error": str(e)})
            raise CacheConnectionError(f"Cache set failed: {e}") from e

    def delete(self, key: str) -> None:
        """Delete key from cache."""
        try:
            self._redis_client.delete(key)
        except redis.RedisError as e:
            logger.error("cache_delete_failed", extra={"key": key, "error": str(e)})
            raise CacheConnectionError(f"Cache delete failed: {e}") from e

    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            return bool(self._redis_client.exists(key))
        except redis.RedisError as e:
            logger.error("cache_exists_failed", extra={"key": key, "error": str(e)})
            raise CacheConnectionError(f"Cache exists check failed: {e}") from e

    def delete_many(self, keys: list[str]) -> None:
        """Delete multiple keys in a single pipeline round-trip."""
        if not keys:
            return
        try:
            with self._redis_client.pipeline() as pipe:
                for key in keys:
                    pipe.delete(key)
                pipe.execute()
        except redis.RedisError as e:
            logger.error(
                "cache_delete_many_failed", extra={"keys": keys, "error": str(e)}
            )
            raise CacheConnectionError(f"Cache delete_many failed: {e}") from e

    def ping(self) -> bool:
        """Return True if Redis is reachable."""
        try:
            return bool(self._redis_client.ping())
        except redis.RedisError:
            return False

    def set_add(self, key: str, value: str) -> None:
        """Add a value to a Redis set."""
        try:
            self._redis_client.sadd(key, value)
        except redis.RedisError as e:
            raise CacheConnectionError(f"set_add failed: {e}") from e

    def set_add_many(self, key: str, values: list[str]) -> None:
        """Add multiple values to a Redis set in one pipeline round-trip."""
        if not values:
            return
        try:
            with self._redis_client.pipeline() as pipe:
                for v in values:
                    pipe.sadd(key, v)
                pipe.execute()
        except redis.RedisError as e:
            raise CacheConnectionError(f"set_add_many failed: {e}") from e

    def set_contains(self, key: str, value: str) -> bool:
        """Return True if value is a member of the set."""
        try:
            return bool(self._redis_client.sismember(key, value))
        except redis.RedisError as e:
            raise CacheConnectionError(f"set_contains failed: {e}") from e

    def set_contains_many(self, key: str, values: list[str]) -> list[bool]:
        """Return membership booleans for each value in one pipeline round-trip."""
        if not values:
            return []
        try:
            with self._redis_client.pipeline() as pipe:
                for v in values:
                    pipe.sismember(key, v)
                return [bool(r) for r in pipe.execute()]
        except redis.RedisError as e:
            raise CacheConnectionError(f"set_contains_many failed: {e}") from e

    def hash_set(self, key: str, field: str, value: str) -> None:
        """Set a field in a Redis hash."""
        try:
            self._redis_client.hset(key, field, value)
        except redis.RedisError as e:
            raise CacheConnectionError(f"hash_set failed: {e}") from e

    def hash_set_many(self, key: str, mapping: dict[str, str]) -> None:
        """Set multiple fields in a Redis hash in one pipeline round-trip."""
        if not mapping:
            return
        try:
            with self._redis_client.pipeline() as pipe:
                for field, value in mapping.items():
                    pipe.hset(key, field, value)
                pipe.execute()
        except redis.RedisError as e:
            raise CacheConnectionError(f"hash_set_many failed: {e}") from e

    def hash_get(self, key: str, field: str) -> str | None:
        """Get a field from a Redis hash. Returns None if missing."""
        try:
            return self._redis_client.hget(key, field)  # type: ignore[return-value]
        except redis.RedisError as e:
            raise CacheConnectionError(f"hash_get failed: {e}") from e

    def expire(self, key: str, seconds: int) -> None:
        """Set a TTL on an existing key. No-op if the key does not exist."""
        try:
            self._redis_client.expire(key, seconds)
        except redis.RedisError as e:
            raise CacheConnectionError(f"expire failed: {e}") from e

    def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching a pattern using SCAN to avoid blocking Redis."""
        try:
            deleted = 0
            cursor = 0
            while True:
                cursor, keys = self._redis_client.scan(cursor, match=pattern, count=100)
                if keys:
                    deleted += self._redis_client.delete(*keys)  # type: ignore[arg-type]
                if cursor == 0:
                    break
            return deleted
        except redis.RedisError as e:
            logger.error(
                "cache_clear_pattern_failed",
                extra={"pattern": pattern, "error": str(e)},
            )
            raise CacheConnectionError(f"Cache pattern clear failed: {e}") from e


def get_redis_connection(redis_url: str) -> redis.Redis:
    """Create Redis connection with connection pooling."""
    try:
        pool = redis.ConnectionPool.from_url(redis_url, decode_responses=True)
        return redis.Redis(connection_pool=pool)
    except redis.RedisError as e:
        logger.error("redis_connection_failed", extra={"error": str(e)})
        raise CacheConnectionError(f"Redis connection failed: {e}") from e
