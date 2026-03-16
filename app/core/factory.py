from collections.abc import Callable

from flask import current_app

from app.core.pathfinding import BidirectionalBFSPathFinder, RedisBasedBFSPathFinder
from app.core.services import (
    CacheManagementService,
    PathFindingService,
    WikipediaService,
)
from app.external.wikipedia import WikipediaClient
from app.infrastructure.cache import RedisCache, get_redis_connection
from app.infrastructure.redis_queue import RedisQueue
from app.utils.constants import ALGORITHM_BIDIRECTIONAL
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ServiceFactory:
    """Factory for creating service instances with proper dependency injection."""

    _redis_client = None
    _cache_service = None
    _queue_service = None
    _wikipedia_client = None

    @classmethod
    def get_redis_client(cls):
        """Get or create Redis client singleton."""
        if cls._redis_client is None:
            redis_url = current_app.config["REDIS_URL"]
            cls._redis_client = get_redis_connection(redis_url)
            logger.info("Redis client created")
        return cls._redis_client

    @classmethod
    def get_cache_service(cls):
        """Get or create cache service singleton."""
        if cls._cache_service is None:
            redis_client = cls.get_redis_client()
            cache_ttl = current_app.config.get("CACHE_TTL", 86400)
            cls._cache_service = RedisCache(redis_client, cache_ttl)
            logger.info("Cache service created")
        return cls._cache_service

    @classmethod
    def get_queue_service(cls):
        """Get or create queue service singleton."""
        if cls._queue_service is None:
            redis_client = cls.get_redis_client()
            cls._queue_service = RedisQueue(redis_client)
            logger.info("Queue service created")
        return cls._queue_service

    @classmethod
    def get_wikipedia_client(cls):
        """Get or create Wikipedia client singleton."""
        if cls._wikipedia_client is None:
            cache_service = cls.get_cache_service()
            max_workers = current_app.config.get("WIKIPEDIA_MAX_WORKERS", 3)
            cache_ttl = current_app.config.get("CACHE_TTL", 86400)
            api_timeout = current_app.config.get("WIKIPEDIA_API_TIMEOUT", 15)
            max_paginate_calls = current_app.config.get(
                "WIKIPEDIA_MAX_PAGINATE_CALLS", 3
            )
            request_delay = current_app.config.get("WIKIPEDIA_REQUEST_DELAY", 0.1)
            max_retries = current_app.config.get("WIKIPEDIA_BACKOFF_MAX_RETRIES", 5)
            cls._wikipedia_client = WikipediaClient(
                cache_service=cache_service,
                max_workers=max_workers,
                cache_ttl=cache_ttl,
                api_timeout=api_timeout,
                max_paginate_calls=max_paginate_calls,
                request_delay=request_delay,
                max_retries=max_retries,
            )
            logger.info("Wikipedia client created with caching enabled")
        return cls._wikipedia_client

    @classmethod
    def create_pathfinding_service(
        cls,
        algorithm: str = ALGORITHM_BIDIRECTIONAL,
        progress_callback: Callable | None = None,
    ) -> PathFindingService:
        """Create pathfinding service with specified algorithm."""
        wikipedia_client = cls.get_wikipedia_client()
        cache_service = cls.get_cache_service()
        queue_service = cls.get_queue_service()

        # Create path finder based on algorithm
        max_depth = current_app.config.get("MAX_SEARCH_DEPTH", 6)
        batch_size = current_app.config.get("BFS_BATCH_SIZE", 20)

        if algorithm.lower() == ALGORITHM_BIDIRECTIONAL:
            path_finder = BidirectionalBFSPathFinder(
                wikipedia_client,
                cache_service,
                queue_service,
                max_depth,
                batch_size,
                progress_callback,
            )
        else:  # Default to regular BFS
            path_finder = RedisBasedBFSPathFinder(
                wikipedia_client,
                cache_service,
                queue_service,
                max_depth,
                batch_size,
                progress_callback,
            )

        return PathFindingService(path_finder, cache_service, wikipedia_client)

    @classmethod
    def create_wikipedia_service(cls) -> WikipediaService:
        """Create Wikipedia service."""
        wikipedia_client = cls.get_wikipedia_client()
        cache_service = cls.get_cache_service()

        return WikipediaService(wikipedia_client, cache_service)

    @classmethod
    def create_cache_management_service(cls) -> CacheManagementService:
        """Create cache management service."""
        cache_service = cls.get_cache_service()
        return CacheManagementService(cache_service)

    @classmethod
    def cleanup(cls):
        """Clean up singleton instances (useful for testing)."""
        if cls._redis_client:
            try:
                cls._redis_client.close()
            except Exception as e:
                logger.error(f"Error closing Redis client: {e}")

        cls._redis_client = None
        cls._cache_service = None
        cls._queue_service = None
        cls._wikipedia_client = None
        logger.info("Service factory cleaned up")


def get_pathfinding_service(
    algorithm: str = ALGORITHM_BIDIRECTIONAL, progress_callback: Callable | None = None
) -> PathFindingService:
    """Convenience function to get pathfinding service."""
    return ServiceFactory.create_pathfinding_service(algorithm, progress_callback)


def get_wikipedia_service() -> WikipediaService:
    """Convenience function to get Wikipedia service."""
    return ServiceFactory.create_wikipedia_service()


def get_cache_management_service() -> CacheManagementService:
    """Convenience function to get cache management service."""
    return ServiceFactory.create_cache_management_service()
