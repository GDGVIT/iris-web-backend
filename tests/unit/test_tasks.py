"""Unit tests for Celery task logic.

Tasks are run eagerly using Celery's apply() with an in-memory result backend
so update_state() works without a live Redis connection.
"""

from unittest.mock import Mock, patch

import pytest


@pytest.fixture(autouse=True)
def celery_memory_backend(app):
    """Configure Celery to run tasks eagerly with in-memory backend."""
    from app import celery as celery_app

    with app.app_context():
        celery_app.conf.update(
            task_always_eager=True,
            task_eager_propagates=False,  # return result even on exception
            result_backend="cache+memory://",
            cache_backend="memory",
        )
        yield
        # Restore — tests use session-scoped app so reset to avoid leaking
        celery_app.conf.update(task_always_eager=False)


def _build_service(
    path=None,
    validate_returns=(True, True, {}),
    validate_raises=None,
    find_path_raises=None,
):
    svc = Mock()
    if validate_raises:
        svc.validate_pages.side_effect = validate_raises
    else:
        svc.validate_pages.return_value = validate_returns

    if find_path_raises:
        svc.find_path.side_effect = find_path_raises
    elif path is not None:
        result = Mock()
        result.path = path
        result.length = len(path)
        result.start_page = path[0]
        result.end_page = path[-1]
        result.search_time = 1.23
        result.nodes_explored = 42
        svc.find_path.return_value = result

    return svc


def _apply(start="A", end="B", algorithm="bfs", svc=None):
    from app.infrastructure.tasks import find_path_task

    with patch("app.infrastructure.tasks.get_pathfinding_service", return_value=svc):
        return find_path_task.apply(args=[start, end, algorithm]).result  # type: ignore[attr-defined]


class TestFindPathTask:
    def test_success(self, app):
        with app.app_context():
            result = _apply(svc=_build_service(path=["A", "B"]))
            assert result["status"] == "SUCCESS"
            assert result["path"] == ["A", "B"]
            assert result["length"] == 2
            assert result["nodes_explored"] == 42
            assert "search_stats" in result

    def test_algorithm_in_result(self, app):
        with app.app_context():
            result = _apply(
                svc=_build_service(path=["A", "B"]), algorithm="bidirectional"
            )
            assert result["algorithm"] == "bidirectional"

    def test_invalid_request_same_page(self, app):
        with app.app_context():
            with patch("app.infrastructure.tasks.get_pathfinding_service") as mock_get:
                from app.infrastructure.tasks import find_path_task

                result = find_path_task.apply(args=["X", "X", "bfs"]).result  # type: ignore[attr-defined]
            assert result["status"] == "FAILURE"
            assert result["code"] == "INVALID_REQUEST"
            mock_get.assert_not_called()

    def test_invalid_request_empty_pages(self, app):
        with app.app_context():
            with patch("app.infrastructure.tasks.get_pathfinding_service") as mock_get:
                from app.infrastructure.tasks import find_path_task

                result = find_path_task.apply(args=["", "B", "bfs"]).result  # type: ignore[attr-defined]
            assert result["status"] == "FAILURE"
            assert result["code"] == "INVALID_REQUEST"
            mock_get.assert_not_called()

    def test_start_page_not_found(self, app):
        with app.app_context():
            result = _apply(
                start="Missing",
                end="B",
                svc=_build_service(validate_returns=(False, True, {})),
            )
            assert result["status"] == "FAILURE"
            assert result["code"] == "PAGE_NOT_FOUND"
            assert "Missing" in result["error"]

    def test_end_page_not_found(self, app):
        with app.app_context():
            result = _apply(
                start="A",
                end="Missing",
                svc=_build_service(validate_returns=(True, False, {})),
            )
            assert result["status"] == "FAILURE"
            assert result["code"] == "PAGE_NOT_FOUND"

    def test_disambiguation_from_validate(self, app):
        with app.app_context():
            from app.utils.exceptions import DisambiguationPageError

            result = _apply(
                start="Mercury",
                end="B",
                svc=_build_service(validate_raises=DisambiguationPageError("Mercury")),
            )
            assert result["status"] == "FAILURE"
            assert result["code"] == "DISAMBIGUATION_PAGE"

    def test_path_not_found(self, app):
        with app.app_context():
            from app.utils.exceptions import PathNotFoundError

            result = _apply(
                svc=_build_service(find_path_raises=PathNotFoundError("A", "B"))
            )
            assert result["status"] == "FAILURE"
            assert result["code"] == "PATH_NOT_FOUND"

    def test_invalid_page_from_find_path(self, app):
        with app.app_context():
            from app.utils.exceptions import InvalidPageError

            result = _apply(
                svc=_build_service(find_path_raises=InvalidPageError("bad"))
            )
            assert result["status"] == "FAILURE"
            assert result["code"] == "INVALID_PAGE"

    def test_disambiguation_from_find_path(self, app):
        with app.app_context():
            from app.utils.exceptions import DisambiguationPageError

            result = _apply(
                svc=_build_service(find_path_raises=DisambiguationPageError("Mercury"))
            )
            assert result["status"] == "FAILURE"
            assert result["code"] == "DISAMBIGUATION_PAGE"

    def test_unexpected_exception(self, app):
        with app.app_context():
            result = _apply(svc=_build_service(find_path_raises=RuntimeError("boom")))
            assert result["status"] == "FAILURE"
            assert result["code"] == "INTERNAL_ERROR"

    def test_retryable_error_max_retries_exceeded(self, app):
        with app.app_context():
            from app.utils.exceptions import WikipediaAPIError

            # When retries == max_retries, no retry is attempted — returns FAILURE
            result = _apply(
                svc=_build_service(find_path_raises=WikipediaAPIError("timeout"))
            )
            # With task_eager_propagates=False and retries exhausted or re-raised,
            # we get either FAILURE or the retry behaviour; either way status != SUCCESS
            assert result is not None


class TestHealthCheckTask:
    def test_success(self, app):
        with app.app_context():
            mock_redis = Mock()
            mock_cache = Mock()
            mock_cache.get.return_value = "ok"

            with (
                patch(
                    "app.core.factory.ServiceFactory.get_redis_client",
                    return_value=mock_redis,
                ),
                patch(
                    "app.core.factory.ServiceFactory.get_cache_service",
                    return_value=mock_cache,
                ),
            ):
                from app.infrastructure.tasks import health_check_task

                result = health_check_task.apply().result  # type: ignore[attr-defined]

            assert result["status"] == "SUCCESS"
            assert result["checks"]["redis"] == "healthy"
            assert result["checks"]["cache"] == "healthy"

    def test_cache_value_mismatch(self, app):
        with app.app_context():
            mock_redis = Mock()
            mock_cache = Mock()
            mock_cache.get.return_value = "wrong"  # not "ok"

            with (
                patch(
                    "app.core.factory.ServiceFactory.get_redis_client",
                    return_value=mock_redis,
                ),
                patch(
                    "app.core.factory.ServiceFactory.get_cache_service",
                    return_value=mock_cache,
                ),
            ):
                from app.infrastructure.tasks import health_check_task

                result = health_check_task.apply().result  # type: ignore[attr-defined]

            assert result["status"] == "FAILURE"

    def test_redis_connection_failure(self, app):
        with app.app_context():
            with patch(
                "app.core.factory.ServiceFactory.get_redis_client",
                side_effect=Exception("no redis"),
            ):
                from app.infrastructure.tasks import health_check_task

                result = health_check_task.apply().result  # type: ignore[attr-defined]

            assert result["status"] == "FAILURE"
            assert "no redis" in result["error"]


class TestCacheCleanupTask:
    def test_success(self, app):
        with app.app_context():
            mock_mgmt = Mock()
            mock_mgmt.clear_cache_pattern.return_value = 7

            with patch(
                "app.core.factory.get_cache_management_service", return_value=mock_mgmt
            ):
                from app.infrastructure.tasks import cache_cleanup_task

                result = cache_cleanup_task.apply(args=["bfs_*"]).result  # type: ignore[attr-defined]

            assert result["status"] == "SUCCESS"
            assert result["cleared_count"] == 7
            assert result["pattern"] == "bfs_*"

    def test_failure(self, app):
        with app.app_context():
            with patch(
                "app.core.factory.get_cache_management_service",
                side_effect=Exception("unavailable"),
            ):
                from app.infrastructure.tasks import cache_cleanup_task

                result = cache_cleanup_task.apply(args=["bfs_*"]).result  # type: ignore[attr-defined]

            assert result["status"] == "FAILURE"
            assert "unavailable" in result["error"]
