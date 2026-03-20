import json
from typing import Any

import redis

from app.core.interfaces import QueueInterface
from app.utils.exceptions import CacheConnectionError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RedisQueue(QueueInterface):
    """Redis-based queue implementation for BFS pathfinding."""

    def __init__(self, redis_client: redis.Redis):
        self._redis_client = redis_client

    def push(self, queue_name: str, item: Any) -> None:
        """Push item to the right side of the queue (FIFO)."""
        try:
            serialized_item = json.dumps(item)
            self._redis_client.rpush(queue_name, serialized_item)
        except (redis.RedisError, TypeError, ValueError) as e:
            logger.error(
                "queue_push_failed", extra={"queue": queue_name, "error": str(e)}
            )
            raise CacheConnectionError(f"Queue push failed: {e}")

    def pop(self, queue_name: str) -> Any | None:
        """Pop item from the left side of the queue (FIFO)."""
        try:
            item = self._redis_client.lpop(queue_name)
            if item is None:
                return None
            return json.loads(item)  # type: ignore[arg-type]
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(
                "queue_pop_failed", extra={"queue": queue_name, "error": str(e)}
            )
            raise CacheConnectionError(f"Queue pop failed: {e}")

    def length(self, queue_name: str) -> int:
        """Get the length of the queue."""
        try:
            return self._redis_client.llen(queue_name)  # type: ignore[return-value]
        except redis.RedisError as e:
            logger.error(
                "queue_length_failed", extra={"queue": queue_name, "error": str(e)}
            )
            raise CacheConnectionError(f"Queue length check failed: {e}")

    def clear(self, queue_name: str) -> None:
        """Clear all items from the queue."""
        try:
            self._redis_client.delete(queue_name)
        except redis.RedisError as e:
            logger.error(
                "queue_clear_failed", extra={"queue": queue_name, "error": str(e)}
            )
            raise CacheConnectionError(f"Queue clear failed: {e}")

    def push_batch(self, queue_name: str, items: list[Any]) -> None:
        """Push multiple items to the queue efficiently using a pipeline."""
        if not items:
            return

        try:
            with self._redis_client.pipeline() as pipe:
                for item in items:
                    pipe.rpush(queue_name, json.dumps(item))
                pipe.execute()
        except (redis.RedisError, TypeError, ValueError) as e:
            logger.error(
                "queue_push_batch_failed", extra={"queue": queue_name, "error": str(e)}
            )
            raise CacheConnectionError(f"Queue batch push failed: {e}")

    def pop_batch(self, queue_name: str, count: int) -> list[Any]:
        """Pop multiple items from the queue efficiently using a pipeline."""
        if count <= 0:
            return []

        try:
            with self._redis_client.pipeline() as pipe:
                for _ in range(count):
                    pipe.lpop(queue_name)
                results = pipe.execute()
            return [json.loads(r) for r in results if r is not None]
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(
                "queue_pop_batch_failed", extra={"queue": queue_name, "error": str(e)}
            )
            raise CacheConnectionError(f"Queue batch pop failed: {e}")
