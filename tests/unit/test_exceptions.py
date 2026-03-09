"""Unit tests for the custom exception hierarchy."""

from app.utils.exceptions import (
    CacheConnectionError,
    CacheError,
    ConfigurationError,
    DisambiguationPageError,
    InvalidPageError,
    IrisBaseException,
    PathFindingError,
    PathNotFoundError,
    TaskError,
    TaskTimeoutError,
    WikipediaAPIError,
    WikipediaError,
    WikipediaPageNotFoundError,
)


class TestIrisBaseException:
    def test_defaults(self):
        exc = IrisBaseException()
        assert exc.message == "An application error occurred"
        assert exc.code == "IrisBaseException"
        assert str(exc) == "An application error occurred"

    def test_custom_message_and_code(self):
        exc = IrisBaseException("oops", "MY_CODE")
        assert exc.message == "oops"
        assert exc.code == "MY_CODE"


class TestWikipediaError:
    def test_with_message(self):
        exc = WikipediaError("custom msg")
        assert exc.message == "custom msg"
        assert exc.code == "WIKIPEDIA_ERROR"
        assert exc.page_title is None

    def test_with_page_title_only(self):
        exc = WikipediaError(page_title="Python")
        assert "Python" in exc.message

    def test_page_not_found(self):
        exc = WikipediaPageNotFoundError("Foo")
        assert "Foo" in exc.message
        assert exc.code == "WIKIPEDIA_PAGE_NOT_FOUND"


class TestWikipediaAPIError:
    def test_default_message(self):
        exc = WikipediaAPIError()
        assert "Wikipedia API request failed" in exc.message
        assert exc.code == "WIKIPEDIA_API_ERROR"
        assert exc.status_code is None

    def test_with_status_code(self):
        exc = WikipediaAPIError(status_code=503)
        assert "503" in exc.message
        assert exc.status_code == 503

    def test_with_explicit_message(self):
        exc = WikipediaAPIError("rate limited")
        assert exc.message == "rate limited"


class TestPathFindingError:
    def test_with_start_and_end(self):
        exc = PathFindingError(start_page="A", end_page="B")
        assert "A" in exc.message and "B" in exc.message
        assert exc.code == "PATHFINDING_ERROR"

    def test_with_explicit_message(self):
        exc = PathFindingError("explicit")
        assert exc.message == "explicit"

    def test_no_args(self):
        exc = PathFindingError()
        assert exc.message is not None  # falls back to base default


class TestPathNotFoundError:
    def test_basic(self):
        exc = PathNotFoundError("Start", "End")
        assert "Start" in exc.message and "End" in exc.message
        assert exc.code == "PATH_NOT_FOUND"
        assert exc.max_depth is None

    def test_with_max_depth(self):
        exc = PathNotFoundError("A", "B", max_depth=6)
        assert "6" in exc.message
        assert exc.max_depth == 6


class TestInvalidPageError:
    def test_with_page_title(self):
        exc = InvalidPageError(page_title="BadPage")
        assert "BadPage" in exc.message
        assert exc.code == "INVALID_PAGE"

    def test_with_explicit_message(self):
        exc = InvalidPageError("explicit error")
        assert exc.message == "explicit error"

    def test_no_args(self):
        exc = InvalidPageError()
        assert exc.message == "Invalid page provided"


class TestDisambiguationPageError:
    def test_without_resolved_title(self):
        exc = DisambiguationPageError("Mercury")
        assert "Mercury" in exc.message
        assert "disambiguation" in exc.message.lower()
        assert exc.code == "DISAMBIGUATION_PAGE"

    def test_with_different_resolved_title(self):
        exc = DisambiguationPageError("Mercury", resolved_title="Mercury (planet)")
        assert "Mercury" in exc.message
        assert "Mercury (planet)" in exc.message

    def test_with_same_resolved_title(self):
        # resolved_title == page_title falls to the plain branch
        exc = DisambiguationPageError("Mercury", resolved_title="Mercury")
        assert "disambiguation" in exc.message.lower()


class TestCacheError:
    def test_default(self):
        exc = CacheError()
        assert exc.message == "Cache operation failed"
        assert exc.code == "CACHE_ERROR"

    def test_with_operation(self):
        exc = CacheError(operation="get")
        assert "get" in exc.message

    def test_with_explicit_message(self):
        exc = CacheError("custom")
        assert exc.message == "custom"


class TestCacheConnectionError:
    def test_default_message(self):
        exc = CacheConnectionError()
        assert "Redis connection failed" in exc.message
        assert exc.code == "CACHE_CONNECTION_ERROR"

    def test_custom_message(self):
        exc = CacheConnectionError("timeout")
        assert "timeout" in exc.message


class TestTaskError:
    def test_default(self):
        exc = TaskError()
        assert exc.message == "Task execution failed"
        assert exc.code == "TASK_ERROR"

    def test_with_task_id(self):
        exc = TaskError(task_id="abc-123")
        assert "abc-123" in exc.message

    def test_with_explicit_message(self):
        exc = TaskError("boom")
        assert exc.message == "boom"


class TestTaskTimeoutError:
    def test_default(self):
        exc = TaskTimeoutError()
        assert "timed out" in exc.message
        assert exc.code == "TASK_TIMEOUT"
        assert exc.timeout is None

    def test_with_task_id(self):
        exc = TaskTimeoutError(task_id="t1")
        assert "t1" in exc.message

    def test_with_timeout(self):
        exc = TaskTimeoutError(timeout=300)
        assert "300" in exc.message

    def test_with_both(self):
        exc = TaskTimeoutError(task_id="t1", timeout=60)
        assert "t1" in exc.message
        assert "60" in exc.message


class TestConfigurationError:
    def test_default(self):
        exc = ConfigurationError()
        assert exc.message == "Configuration error"
        assert exc.code == "CONFIGURATION_ERROR"

    def test_with_config_key(self):
        exc = ConfigurationError(config_key="SECRET_KEY")
        assert "SECRET_KEY" in exc.message

    def test_with_explicit_message(self):
        exc = ConfigurationError("missing value")
        assert exc.message == "missing value"
