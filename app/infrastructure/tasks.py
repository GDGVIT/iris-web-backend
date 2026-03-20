from typing import TypedDict

import requests
from celery.schedules import crontab
from flask import current_app

from app import celery
from app.core.factory import (
    ServiceFactory,
    get_cache_management_service,
    get_pathfinding_service,
)
from app.core.models import SearchRequest
from app.utils.constants import (
    ALGORITHM_BIDIRECTIONAL,
    BFS_CACHE_CLEANUP_PATTERN,
    CELERY_STATE_FAILURE,
    CELERY_STATE_PROGRESS,
    CELERY_STATE_RETRY,
    CELERY_STATE_SUCCESS,
    ERROR_DISAMBIGUATION_PAGE,
    ERROR_INTERNAL_ERROR,
    ERROR_INVALID_PAGE,
    ERROR_INVALID_REQUEST,
    ERROR_MAX_RETRIES_EXCEEDED,
    ERROR_PAGE_NOT_FOUND,
    ERROR_PATH_NOT_FOUND,
    HEALTH_CHECK_CACHE_KEY,
    PERIODIC_TASK_CLEANUP_BFS,
    PERIODIC_TASK_HEALTH_CHECK,
    QUEUE_HEALTH,
    QUEUE_MAINTENANCE,
    QUEUE_PATHFINDING,
    TASK_FQN_CACHE_CLEANUP,
    TASK_FQN_FIND_PATH,
    TASK_FQN_HEALTH_CHECK,
)
from app.utils.exceptions import (
    CacheConnectionError,
    DisambiguationPageError,
    InvalidPageError,
    PathNotFoundError,
    WikipediaAPIError,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


class FindPathResult(TypedDict, total=False):
    """Typed contract for find_path_task return values.

    All paths guarantee: status, start_page, end_page.
    Failure paths add: error, code.
    Success path adds: path, length, search_time, nodes_explored, algorithm, search_stats.
    Retry-exhaustion adds: retry_count.
    """

    status: str
    start_page: str
    end_page: str
    error: str
    code: str
    path: list[str]
    length: int
    search_time: float | None
    nodes_explored: int | None
    algorithm: str
    search_stats: dict
    retry_count: int


@celery.task(
    bind=True,
    autoretry_for=(requests.RequestException, CacheConnectionError, WikipediaAPIError),
    retry_kwargs={"max_retries": 3, "countdown": 60},
)
def find_path_task(
    self, start_page: str, end_page: str, algorithm: str = ALGORITHM_BIDIRECTIONAL
) -> FindPathResult:
    """
    Celery task for finding a path between Wikipedia pages.

    Args:
        start_page: Starting Wikipedia page title
        end_page: Target Wikipedia page title
        algorithm: Pathfinding algorithm to use ('bfs' or 'bidirectional')

    Returns:
        Dictionary with path result or error information
    """
    task_id = self.request.id
    logger.info(
        "pathfinding_started",
        extra={
            "task_id": task_id,
            "start_page": start_page,
            "end_page": end_page,
            "algorithm": algorithm,
        },
    )

    try:
        # Update task state to IN_PROGRESS
        self.update_state(
            state=CELERY_STATE_PROGRESS,
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
            logger.error("invalid_search_request", extra={"task_id": task_id})
            return {
                "status": CELERY_STATE_FAILURE,
                "error": "Invalid search request: start and end pages must be different and non-empty",
                "code": ERROR_INVALID_REQUEST,
                "start_page": start_page,
                "end_page": end_page,
            }

        # Update progress
        self.update_state(
            state=CELERY_STATE_PROGRESS,
            meta={
                "current": 10,
                "total": 100,
                "status": "Validating pages...",
                "start_page": start_page,
                "end_page": end_page,
            },
        )

        # Create progress callback for real-time updates.
        # The pathfinder supplies whatever fields it knows; we enrich with
        # task-level context (start_page, end_page, max_depth) here.
        max_depth = current_app.config.get("MAX_SEARCH_DEPTH", 6)

        def progress_update(progress_data):
            if "search_stats" not in progress_data:
                progress_data = {
                    "status": "Searching...",
                    "search_stats": progress_data,
                    "search_time_elapsed": progress_data.get("search_time_elapsed", 0),
                }
            search_stats: dict = progress_data["search_stats"]  # type: ignore[assignment]
            search_stats.setdefault("start_page", start_page)
            search_stats.setdefault("end_page", end_page)
            search_stats.setdefault("max_depth", max_depth)

            self.update_state(state=CELERY_STATE_PROGRESS, meta=progress_data)

        # Get pathfinding service with progress callback
        pathfinding_service = get_pathfinding_service(algorithm, progress_update)

        # Validate that pages exist and check for disambiguation issues
        try:
            start_exists, end_exists, _ = pathfinding_service.validate_pages(
                start_page, end_page
            )
        except DisambiguationPageError as e:
            logger.error(
                "disambiguation_page_error", extra={"task_id": task_id, "error": str(e)}
            )
            return {
                "status": CELERY_STATE_FAILURE,
                "error": str(e),
                "code": ERROR_DISAMBIGUATION_PAGE,
                "start_page": start_page,
                "end_page": end_page,
            }

        if not start_exists:
            logger.error(
                "start_page_not_found",
                extra={"task_id": task_id, "start_page": start_page},
            )
            return {
                "status": CELERY_STATE_FAILURE,
                "error": f"Start page '{start_page}' does not exist on Wikipedia",
                "code": ERROR_PAGE_NOT_FOUND,
                "start_page": start_page,
                "end_page": end_page,
            }

        if not end_exists:
            logger.error(
                "end_page_not_found", extra={"task_id": task_id, "end_page": end_page}
            )
            return {
                "status": CELERY_STATE_FAILURE,
                "error": f"End page '{end_page}' does not exist on Wikipedia",
                "code": ERROR_PAGE_NOT_FOUND,
                "start_page": start_page,
                "end_page": end_page,
            }

        # Update progress - starting search
        self.update_state(
            state=CELERY_STATE_PROGRESS,
            meta={
                "status": "Starting pathfinding search...",
                "search_stats": {
                    "nodes_explored": 0,
                    "current_depth": 0,
                    "last_node": start_page,
                    "queue_size": 1,
                    "start_page": start_page,
                    "end_page": end_page,
                    "max_depth": max_depth,
                },
                "search_time_elapsed": 0,
            },
        )

        # Perform pathfinding (will report real-time progress via callback)
        result = pathfinding_service.find_path(search_request)

        # Return successful result with detailed search stats
        success_result: FindPathResult = {
            "status": CELERY_STATE_SUCCESS,
            "path": result.path,
            "length": result.length,
            "start_page": result.start_page,
            "end_page": result.end_page,
            "search_time": result.search_time,
            "nodes_explored": result.nodes_explored,
            "algorithm": algorithm,
            "search_stats": {
                "nodes_explored": result.nodes_explored,
                "final_depth": result.length - 1 if result.path else 0,
                "start_page": result.start_page,
                "end_page": result.end_page,
                "max_depth": max_depth,
                "search_completed": True,
            },
        }

        logger.info(
            "pathfinding_completed",
            extra={
                "task_id": task_id,
                "path_length": result.length,
                "search_time": round(result.search_time or 0.0, 3),
            },
        )
        return success_result

    except PathNotFoundError as e:
        logger.warning("path_not_found", extra={"task_id": task_id, "error": str(e)})
        return {
            "status": CELERY_STATE_FAILURE,
            "error": str(e),
            "code": ERROR_PATH_NOT_FOUND,
            "start_page": start_page,
            "end_page": end_page,
        }

    except InvalidPageError as e:
        logger.error("invalid_page", extra={"task_id": task_id, "error": str(e)})
        return {
            "status": CELERY_STATE_FAILURE,
            "error": str(e),
            "code": ERROR_INVALID_PAGE,
            "start_page": start_page,
            "end_page": end_page,
        }

    except DisambiguationPageError as e:
        logger.error(
            "disambiguation_page_error", extra={"task_id": task_id, "error": str(e)}
        )
        return {
            "status": CELERY_STATE_FAILURE,
            "error": str(e),
            "code": ERROR_DISAMBIGUATION_PAGE,
            "start_page": start_page,
            "end_page": end_page,
        }

    except (requests.RequestException, CacheConnectionError, WikipediaAPIError) as e:
        # These exceptions trigger auto-retry
        logger.warning("retryable_error", extra={"task_id": task_id, "error": str(e)})

        # Update retry count in task state
        retry_count = self.request.retries
        max_retries = self.retry_kwargs.get("max_retries", 3)

        if retry_count < max_retries:
            self.update_state(
                state=CELERY_STATE_RETRY,
                meta={
                    "error": str(e),
                    "retry_count": retry_count + 1,
                    "max_retries": max_retries,
                    "next_retry_in": 60,
                    "status": f"Retrying due to: {str(e)}",
                },
            )

            # Re-raise to trigger Celery's retry mechanism
            raise self.retry(exc=e) from e
        else:
            logger.error(
                "max_retries_exceeded", extra={"task_id": task_id, "error": str(e)}
            )
            return {
                "status": CELERY_STATE_FAILURE,
                "error": f"Max retries exceeded. Last error: {str(e)}",
                "code": ERROR_MAX_RETRIES_EXCEEDED,
                "start_page": start_page,
                "end_page": end_page,
                "retry_count": retry_count,
            }

    except Exception as e:
        # Unexpected errors - don't retry
        logger.error(
            "unexpected_error",
            extra={"task_id": task_id, "error": str(e)},
            exc_info=True,
        )
        return {
            "status": CELERY_STATE_FAILURE,
            "error": f"Unexpected error: {str(e)}",
            "code": ERROR_INTERNAL_ERROR,
            "start_page": start_page,
            "end_page": end_page,
        }


@celery.task(bind=True)
def health_check_task(self):
    """
    Celery task for health checking - verifies Celery worker is functioning.

    Returns:
        Dictionary with health check result
    """
    task_id = self.request.id
    logger.info("health_check_started", extra={"task_id": task_id})

    try:
        # Perform basic health checks
        # Test cache service (ping also validates Redis connectivity)
        cache_service = ServiceFactory.get_cache_service()
        if not cache_service.ping():
            raise Exception("Redis ping failed")
        test_key = f"{HEALTH_CHECK_CACHE_KEY}_{task_id}"
        cache_service.set(test_key, "ok", ttl=60)
        cache_value = cache_service.get(test_key)
        cache_service.delete(test_key)

        if cache_value != "ok":
            raise Exception("Cache test failed")

        logger.info("health_check_completed", extra={"task_id": task_id})
        return {
            "status": CELERY_STATE_SUCCESS,
            "message": "Celery worker is healthy",
            "task_id": task_id,
            "checks": {"redis": "healthy", "cache": "healthy"},
        }

    except Exception as e:
        logger.error("health_check_failed", extra={"task_id": task_id, "error": str(e)})
        return {"status": CELERY_STATE_FAILURE, "error": str(e), "task_id": task_id}


@celery.task(bind=True)
def cache_cleanup_task(self, pattern: str = BFS_CACHE_CLEANUP_PATTERN):
    """
    Celery task for cleaning up expired cache entries.

    Args:
        pattern: Redis key pattern to clean up

    Returns:
        Dictionary with cleanup result
    """
    task_id = self.request.id
    logger.info("cache_cleanup_started", extra={"task_id": task_id, "pattern": pattern})

    try:
        cache_service = get_cache_management_service()
        cleared_count = cache_service.clear_cache_pattern(pattern)

        logger.info(
            "cache_cleanup_completed",
            extra={"task_id": task_id, "cleared_count": cleared_count},
        )
        return {
            "status": CELERY_STATE_SUCCESS,
            "message": f"Cleared {cleared_count} cache entries",
            "pattern": pattern,
            "cleared_count": cleared_count,
            "task_id": task_id,
        }

    except Exception as e:
        logger.error(
            "cache_cleanup_failed", extra={"task_id": task_id, "error": str(e)}
        )
        return {
            "status": CELERY_STATE_FAILURE,
            "error": str(e),
            "pattern": pattern,
            "task_id": task_id,
        }


# Task routing and configuration
def configure_task_routes(app):
    """Configure Celery task routes and settings."""

    # Task routes - can be used to route tasks to specific workers
    app.conf.task_routes = {
        TASK_FQN_FIND_PATH: {"queue": QUEUE_PATHFINDING},
        TASK_FQN_HEALTH_CHECK: {"queue": QUEUE_HEALTH},
        TASK_FQN_CACHE_CLEANUP: {"queue": QUEUE_MAINTENANCE},
    }

    # Task result settings
    app.conf.result_expires = 3600  # Results expire after 1 hour
    app.conf.result_persistent = True

    # Task retry settings
    app.conf.task_reject_on_worker_lost = True

    logger.info("Celery task configuration applied")


# Periodic tasks (if using celery beat)
app_periodic_tasks = {
    # Clean up old BFS search state every hour
    PERIODIC_TASK_CLEANUP_BFS: {
        "task": TASK_FQN_CACHE_CLEANUP,
        "schedule": crontab(minute=0),  # Every hour
        "args": (BFS_CACHE_CLEANUP_PATTERN,),
    },
    # Health check every 5 minutes
    PERIODIC_TASK_HEALTH_CHECK: {
        "task": TASK_FQN_HEALTH_CHECK,
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
}


def configure_periodic_tasks(app):
    """Configure periodic tasks if Celery Beat is enabled."""
    app.conf.beat_schedule = app_periodic_tasks
    app.conf.timezone = "UTC"
    logger.info("Celery periodic tasks configured")
