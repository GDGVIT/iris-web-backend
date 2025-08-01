import redis
import json
from typing import Any, Optional
from app.core.interfaces import CacheServiceInterface
from app.utils.exceptions import CacheConnectionError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RedisCache(CacheServiceInterface):
    """Redis-based cache implementation."""

    def __init__(self, redis_client: redis.Redis, default_ttl: int = 86400):
        self.redis_client = redis_client
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache by key."""
        try:
            value = self.redis_client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Failed to get value from cache for key {key}: {e}")
            raise CacheConnectionError(f"Cache get failed: {e}")

    def set(self, key: str, value: Any, ttl: int = None) -> None:
        """Set value in cache with optional TTL."""
        try:
            ttl = ttl or self.default_ttl
            serialized_value = json.dumps(value)
            self.redis_client.setex(key, ttl, serialized_value)
        except (redis.RedisError, json.JSONEncodeError) as e:
            logger.error(f"Failed to set value in cache for key {key}: {e}")
            raise CacheConnectionError(f"Cache set failed: {e}")

    def delete(self, key: str) -> None:
        """Delete key from cache."""
        try:
            self.redis_client.delete(key)
        except redis.RedisError as e:
            logger.error(f"Failed to delete key from cache: {key}: {e}")
            raise CacheConnectionError(f"Cache delete failed: {e}")

    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            return bool(self.redis_client.exists(key))
        except redis.RedisError as e:
            logger.error(f"Failed to check key existence in cache: {key}: {e}")
            raise CacheConnectionError(f"Cache exists check failed: {e}")

    def get_links_from_cache(self, page_title: str) -> Optional[list]:
        """Retrieves a list of links for a Wikipedia page from the cache."""
        cache_key = f"wiki_links:{page_title}"
        return self.get(cache_key)

    def set_links_in_cache(self, page_title: str, links: list, ttl: int = None) -> None:
        """Stores a list of links for a page in the cache."""
        cache_key = f"wiki_links:{page_title}"
        self.set(cache_key, links, ttl)

    def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching a pattern."""
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except redis.RedisError as e:
            logger.error(f"Failed to clear keys with pattern {pattern}: {e}")
            raise CacheConnectionError(f"Cache pattern clear failed: {e}")

    def get_ttl(self, key: str) -> int:
        """Get TTL for a key."""
        try:
            return self.redis_client.ttl(key)
        except redis.RedisError as e:
            logger.error(f"Failed to get TTL for key {key}: {e}")
            return -1

    def increment(self, key: str, amount: int = 1) -> int:
        """Increment a numeric value in cache."""
        try:
            return self.redis_client.incrby(key, amount)
        except redis.RedisError as e:
            logger.error(f"Failed to increment key {key}: {e}")
            raise CacheConnectionError(f"Cache increment failed: {e}")

    def set_if_not_exists(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value only if key doesn't exist."""
        try:
            ttl = ttl or self.default_ttl
            serialized_value = json.dumps(value)
            return bool(self.redis_client.set(key, serialized_value, ex=ttl, nx=True))
        except (redis.RedisError, json.JSONEncodeError) as e:
            logger.error(f"Failed to set value if not exists for key {key}: {e}")
            raise CacheConnectionError(f"Cache set if not exists failed: {e}")


def get_redis_connection(redis_url: str) -> redis.Redis:
    """Create Redis connection with connection pooling."""
    try:
        pool = redis.ConnectionPool.from_url(redis_url, decode_responses=True)
        return redis.Redis(connection_pool=pool)
    except redis.RedisError as e:
        logger.error(f"Failed to create Redis connection: {e}")
        raise CacheConnectionError(f"Redis connection failed: {e}")
