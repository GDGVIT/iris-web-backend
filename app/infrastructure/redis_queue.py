import json
import redis
from typing import Any, Optional, List
from app.core.interfaces import QueueInterface
from app.utils.exceptions import CacheConnectionError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RedisQueue(QueueInterface):
    """Redis-based queue implementation for BFS pathfinding."""

    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client

    def push(self, queue_name: str, item: Any) -> None:
        """Push item to the right side of the queue (FIFO)."""
        try:
            serialized_item = json.dumps(item)
            self.redis_client.rpush(queue_name, serialized_item)
        except (redis.RedisError, json.JSONEncodeError) as e:
            logger.error(f"Failed to push item to queue {queue_name}: {e}")
            raise CacheConnectionError(f"Queue push failed: {e}")

    def push_front(self, queue_name: str, item: Any) -> None:
        """Push item to the front (left side) of the queue."""
        try:
            serialized_item = json.dumps(item)
            self.redis_client.lpush(queue_name, serialized_item)
        except (redis.RedisError, json.JSONEncodeError) as e:
            logger.error(f"Failed to push item to front of queue {queue_name}: {e}")
            raise CacheConnectionError(f"Queue push front failed: {e}")

    def pop(self, queue_name: str) -> Optional[Any]:
        """Pop item from the left side of the queue (FIFO)."""
        try:
            item = self.redis_client.lpop(queue_name)
            if item is None:
                return None
            return json.loads(item)
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Failed to pop item from queue {queue_name}: {e}")
            raise CacheConnectionError(f"Queue pop failed: {e}")

    def length(self, queue_name: str) -> int:
        """Get the length of the queue."""
        try:
            return self.redis_client.llen(queue_name)
        except redis.RedisError as e:
            logger.error(f"Failed to get queue length for {queue_name}: {e}")
            raise CacheConnectionError(f"Queue length check failed: {e}")

    def clear(self, queue_name: str) -> None:
        """Clear all items from the queue."""
        try:
            self.redis_client.delete(queue_name)
        except redis.RedisError as e:
            logger.error(f"Failed to clear queue {queue_name}: {e}")
            raise CacheConnectionError(f"Queue clear failed: {e}")

    def push_batch(self, queue_name: str, items: List[Any]) -> None:
        """Push multiple items to the queue efficiently."""
        if not items:
            return

        try:
            serialized_items = [json.dumps(item) for item in items]
            self.redis_client.rpush(queue_name, *serialized_items)
        except (redis.RedisError, json.JSONEncodeError) as e:
            logger.error(f"Failed to push batch to queue {queue_name}: {e}")
            raise CacheConnectionError(f"Queue batch push failed: {e}")

    def pop_batch(self, queue_name: str, count: int) -> List[Any]:
        """Pop multiple items from the queue efficiently."""
        if count <= 0:
            return []

        try:
            items = []
            for _ in range(count):
                item = self.redis_client.lpop(queue_name)
                if item is None:
                    break
                items.append(json.loads(item))
            return items
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Failed to pop batch from queue {queue_name}: {e}")
            raise CacheConnectionError(f"Queue batch pop failed: {e}")

    def peek(self, queue_name: str, index: int = 0) -> Optional[Any]:
        """Peek at an item in the queue without removing it."""
        try:
            item = self.redis_client.lindex(queue_name, index)
            if item is None:
                return None
            return json.loads(item)
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Failed to peek at queue {queue_name}: {e}")
            return None
