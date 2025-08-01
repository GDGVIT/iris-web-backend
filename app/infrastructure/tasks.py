import requests
from app import celery
from app.core.factory import get_pathfinding_service
from app.core.models import SearchRequest
from app.utils.exceptions import (
    PathNotFoundError,
    InvalidPageError,
    WikipediaAPIError,
    CacheConnectionError,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


@celery.task(
    bind=True,
    autoretry_for=(requests.RequestException, CacheConnectionError, WikipediaAPIError),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    soft_time_limit=300,  # 5 minutes
    time_limit=600,  # 10 minutes
)
def find_path_task(self, start_page: str, end_page: str, algorithm: str = "bfs"):
    """
    Celery task for finding shortest path between Wikipedia pages.

    Args:
        start_page: Starting Wikipedia page title
        end_page: Target Wikipedia page title
        algorithm: Pathfinding algorithm to use ('bfs' or 'bidirectional')

    Returns:
        Dictionary with path result or error information
    """
    task_id = self.request.id
    logger.info(
        f"Starting pathfinding task {task_id}: {start_page} -> {end_page} (algorithm: {algorithm})"
    )

    try:
        # Update task state to IN_PROGRESS
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 0,
                "total": 100,
                "status": "Initializing pathfinding...",
                "start_page": start_page,
                "end_page": end_page,
            },
        )

        # Create search request
        search_request = SearchRequest(
            start_page=start_page, end_page=end_page, algorithm=algorithm
        )

        # Validate request
        if not search_request.validate():
            logger.error(f"Task {task_id}: Invalid search request")
            return {
                "status": "FAILURE",
                "error": "Invalid search request: start and end pages must be different and non-empty",
                "code": "INVALID_REQUEST",
            }

        # Update progress
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 10,
                "total": 100,
                "status": "Validating pages...",
                "start_page": start_page,
                "end_page": end_page,
            },
        )

        # Get pathfinding service
        pathfinding_service = get_pathfinding_service(algorithm)

        # Validate that pages exist
        start_exists, end_exists = pathfinding_service.validate_pages(
            start_page, end_page
        )

        if not start_exists:
            logger.error(f"Task {task_id}: Start page '{start_page}' does not exist")
            return {
                "status": "FAILURE",
                "error": f"Start page '{start_page}' does not exist on Wikipedia",
                "code": "PAGE_NOT_FOUND",
            }

        if not end_exists:
            logger.error(f"Task {task_id}: End page '{end_page}' does not exist")
            return {
                "status": "FAILURE",
                "error": f"End page '{end_page}' does not exist on Wikipedia",
                "code": "PAGE_NOT_FOUND",
            }

        # Update progress
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 25,
                "total": 100,
                "status": "Starting pathfinding search...",
                "start_page": start_page,
                "end_page": end_page,
            },
        )

        # Perform pathfinding
        result = pathfinding_service.find_path(search_request)

        # Update progress
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 90,
                "total": 100,
                "status": "Finalizing results...",
                "path_length": result.length,
                "search_time": result.search_time,
            },
        )

        # Return successful result
        success_result = {
            "status": "SUCCESS",
            "path": result.path,
            "length": result.length,
            "start_page": result.start_page,
            "end_page": result.end_page,
            "search_time": result.search_time,
            "nodes_explored": result.nodes_explored,
            "algorithm": algorithm,
        }

        logger.info(
            f"Task {task_id} completed successfully: path length {result.length}, time {result.search_time:.2f}s"
        )
        return success_result

    except PathNotFoundError as e:
        logger.warning(f"Task {task_id}: No path found - {e}")
        return {
            "status": "FAILURE",
            "error": str(e),
            "code": "PATH_NOT_FOUND",
            "start_page": start_page,
            "end_page": end_page,
        }

    except InvalidPageError as e:
        logger.error(f"Task {task_id}: Invalid page - {e}")
        return {
            "status": "FAILURE",
            "error": str(e),
            "code": "INVALID_PAGE",
            "start_page": start_page,
            "end_page": end_page,
        }

    except (requests.RequestException, CacheConnectionError, WikipediaAPIError) as e:
        # These exceptions trigger auto-retry
        logger.warning(f"Task {task_id}: Retryable error - {e}")

        # Update retry count in task state
        retry_count = self.request.retries
        max_retries = self.retry_kwargs.get("max_retries", 3)

        if retry_count < max_retries:
            self.update_state(
                state="RETRY",
                meta={
                    "error": str(e),
                    "retry_count": retry_count + 1,
                    "max_retries": max_retries,
                    "next_retry_in": 60,
                    "status": f"Retrying due to: {str(e)}",
                },
            )

            # Re-raise to trigger Celery's retry mechanism
            raise self.retry(exc=e)
        else:
            logger.error(f"Task {task_id}: Max retries exceeded - {e}")
            return {
                "status": "FAILURE",
                "error": f"Max retries exceeded. Last error: {str(e)}",
                "code": "MAX_RETRIES_EXCEEDED",
                "retry_count": retry_count,
            }

    except Exception as e:
        # Unexpected errors - don't retry
        logger.error(f"Task {task_id}: Unexpected error - {e}", exc_info=True)
        return {
            "status": "FAILURE",
            "error": f"Unexpected error: {str(e)}",
            "code": "INTERNAL_ERROR",
        }


@celery.task(bind=True)
def health_check_task(self):
    """
    Celery task for health checking - verifies Celery worker is functioning.

    Returns:
        Dictionary with health check result
    """
    task_id = self.request.id
    logger.info(f"Health check task {task_id} started")

    try:
        # Perform basic health checks
        from app.core.factory import ServiceFactory

        # Test Redis connection
        redis_client = ServiceFactory.get_redis_client()
        redis_client.ping()

        # Test cache service
        cache_service = ServiceFactory.get_cache_service()
        test_key = f"health_check_{task_id}"
        cache_service.set(test_key, "ok", ttl=60)
        cache_value = cache_service.get(test_key)
        cache_service.delete(test_key)

        if cache_value != "ok":
            raise Exception("Cache test failed")

        logger.info(f"Health check task {task_id} completed successfully")
        return {
            "status": "SUCCESS",
            "message": "Celery worker is healthy",
            "task_id": task_id,
            "checks": {"redis": "healthy", "cache": "healthy"},
        }

    except Exception as e:
        logger.error(f"Health check task {task_id} failed: {e}")
        return {"status": "FAILURE", "error": str(e), "task_id": task_id}


@celery.task(bind=True)
def cache_cleanup_task(self, pattern: str = "bfs_*"):
    """
    Celery task for cleaning up expired cache entries.

    Args:
        pattern: Redis key pattern to clean up

    Returns:
        Dictionary with cleanup result
    """
    task_id = self.request.id
    logger.info(f"Cache cleanup task {task_id} started with pattern: {pattern}")

    try:
        from app.core.factory import get_cache_management_service

        cache_service = get_cache_management_service()
        cleared_count = cache_service.clear_cache_pattern(pattern)

        logger.info(
            f"Cache cleanup task {task_id} completed: cleared {cleared_count} entries"
        )
        return {
            "status": "SUCCESS",
            "message": f"Cleared {cleared_count} cache entries",
            "pattern": pattern,
            "cleared_count": cleared_count,
            "task_id": task_id,
        }

    except Exception as e:
        logger.error(f"Cache cleanup task {task_id} failed: {e}")
        return {
            "status": "FAILURE",
            "error": str(e),
            "pattern": pattern,
            "task_id": task_id,
        }


# Task routing and configuration
def configure_task_routes(app):
    """Configure Celery task routes and settings."""

    # Task routes - can be used to route tasks to specific workers
    app.conf.task_routes = {
        "app.infrastructure.tasks.find_path_task": {"queue": "pathfinding"},
        "app.infrastructure.tasks.health_check_task": {"queue": "health"},
        "app.infrastructure.tasks.cache_cleanup_task": {"queue": "maintenance"},
    }

    # Task time limits
    app.conf.task_time_limit = 600  # 10 minutes hard limit
    app.conf.task_soft_time_limit = 300  # 5 minutes soft limit

    # Task result settings
    app.conf.result_expires = 3600  # Results expire after 1 hour
    app.conf.result_persistent = True

    # Task execution settings
    app.conf.task_acks_late = True
    app.conf.worker_prefetch_multiplier = 1

    # Task retry settings
    app.conf.task_reject_on_worker_lost = True

    logger.info("Celery task configuration applied")


# Periodic tasks (if using celery beat)
from celery.schedules import crontab

app_periodic_tasks = {
    # Clean up old BFS search state every hour
    "cleanup-bfs-cache": {
        "task": "app.infrastructure.tasks.cache_cleanup_task",
        "schedule": crontab(minute=0),  # Every hour
        "args": ("bfs_*",),
    },
    # Health check every 5 minutes
    "health-check": {
        "task": "app.infrastructure.tasks.health_check_task",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
}


def configure_periodic_tasks(app):
    """Configure periodic tasks if Celery Beat is enabled."""
    app.conf.beat_schedule = app_periodic_tasks
    app.conf.timezone = "UTC"
    logger.info("Celery periodic tasks configured")
