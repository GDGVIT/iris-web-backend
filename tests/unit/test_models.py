from app.core.models import (
    PathResult,
    ExploreResult,
    SearchRequest,
    ExploreRequest,
    WikipediaPage,
    TaskStatus,
    TaskInfo,
    CacheStats,
    HealthStatus,
)


class TestPathResult:
    """Unit tests for PathResult model."""

    def test_valid_path_result(self):
        """Test creating a valid PathResult."""
        result = PathResult(
            path=["Page A", "Page B", "Page C"],
            length=3,
            start_page="Page A",
            end_page="Page C",
            search_time=1.5,
            nodes_explored=10,
        )

        assert result.path == ["Page A", "Page B", "Page C"]
        assert result.length == 3
        assert result.start_page == "Page A"
        assert result.end_page == "Page C"
        assert result.search_time == 1.5
        assert result.nodes_explored == 10
        assert result.is_valid is True

    def test_invalid_path_result_wrong_start(self):
        """Test PathResult with wrong start page."""
        result = PathResult(
            path=["Page X", "Page B", "Page C"],
            length=3,
            start_page="Page A",  # Different from path[0]
            end_page="Page C",
        )

        assert result.is_valid is False

    def test_invalid_path_result_wrong_end(self):
        """Test PathResult with wrong end page."""
        result = PathResult(
            path=["Page A", "Page B", "Page C"],
            length=3,
            start_page="Page A",
            end_page="Page X",  # Different from path[-1]
        )

        assert result.is_valid is False

    def test_invalid_path_result_wrong_length(self):
        """Test PathResult with wrong length."""
        result = PathResult(
            path=["Page A", "Page B", "Page C"],
            length=5,  # Wrong length
            start_page="Page A",
            end_page="Page C",
        )

        assert result.is_valid is False

    def test_path_result_too_short(self):
        """Test PathResult with path too short."""
        result = PathResult(
            path=["Page A"],  # Only one page
            length=1,
            start_page="Page A",
            end_page="Page A",
        )

        assert result.is_valid is False


class TestExploreResult:
    """Unit tests for ExploreResult model."""

    def test_valid_explore_result(self):
        """Test creating a valid ExploreResult."""
        result = ExploreResult(
            start_page="Test Page",
            nodes=["Test Page", "Link 1", "Link 2"],
            edges=[("Test Page", "Link 1"), ("Test Page", "Link 2")],
            total_links=2,
        )

        assert result.start_page == "Test Page"
        assert result.nodes == ["Test Page", "Link 1", "Link 2"]
        assert result.edges == [("Test Page", "Link 1"), ("Test Page", "Link 2")]
        assert result.total_links == 2
        assert result.is_valid is True

    def test_invalid_explore_result_start_not_in_nodes(self):
        """Test ExploreResult where start page is not in nodes."""
        result = ExploreResult(
            start_page="Test Page",
            nodes=["Link 1", "Link 2"],  # Start page not included
            edges=[("Test Page", "Link 1"), ("Test Page", "Link 2")],
            total_links=2,
        )

        assert result.is_valid is False

    def test_invalid_explore_result_empty_nodes(self):
        """Test ExploreResult with empty nodes."""
        result = ExploreResult(
            start_page="Test Page", nodes=[], edges=[], total_links=0  # Empty nodes
        )

        assert result.is_valid is False

    def test_invalid_explore_result_negative_total_links(self):
        """Test ExploreResult with negative total links."""
        result = ExploreResult(
            start_page="Test Page",
            nodes=["Test Page"],
            edges=[],
            total_links=-1,  # Negative total links
        )

        assert result.is_valid is False


class TestSearchRequest:
    """Unit tests for SearchRequest model."""

    def test_valid_search_request(self):
        """Test creating a valid SearchRequest."""
        request = SearchRequest(
            start_page="Page A", end_page="Page B", max_depth=5, algorithm="bfs"
        )

        assert request.start_page == "Page A"
        assert request.end_page == "Page B"
        assert request.max_depth == 5
        assert request.algorithm == "bfs"
        assert request.validate() is True

    def test_search_request_minimal(self):
        """Test SearchRequest with minimal required fields."""
        request = SearchRequest(start_page="Page A", end_page="Page B")

        assert request.start_page == "Page A"
        assert request.end_page == "Page B"
        assert request.max_depth is None
        assert request.algorithm == "bfs"
        assert request.validate() is True

    def test_invalid_search_request_empty_start(self):
        """Test SearchRequest with empty start page."""
        request = SearchRequest(start_page="", end_page="Page B")

        assert request.validate() is False

    def test_invalid_search_request_empty_end(self):
        """Test SearchRequest with empty end page."""
        request = SearchRequest(start_page="Page A", end_page="")

        assert request.validate() is False

    def test_invalid_search_request_same_pages(self):
        """Test SearchRequest with same start and end pages."""
        request = SearchRequest(start_page="Page A", end_page="Page A")

        assert request.validate() is False

    def test_invalid_search_request_whitespace_only(self):
        """Test SearchRequest with whitespace-only pages."""
        request = SearchRequest(start_page="   ", end_page="Page B")

        assert request.validate() is False


class TestExploreRequest:
    """Unit tests for ExploreRequest model."""

    def test_valid_explore_request(self):
        """Test creating a valid ExploreRequest."""
        request = ExploreRequest(start_page="Test Page", max_links=15)

        assert request.start_page == "Test Page"
        assert request.max_links == 15
        assert request.validate() is True

    def test_explore_request_minimal(self):
        """Test ExploreRequest with minimal required fields."""
        request = ExploreRequest(start_page="Test Page")

        assert request.start_page == "Test Page"
        assert request.max_links is None
        assert request.validate() is True

    def test_invalid_explore_request_empty_start(self):
        """Test ExploreRequest with empty start page."""
        request = ExploreRequest(start_page="")

        assert request.validate() is False

    def test_invalid_explore_request_whitespace_only(self):
        """Test ExploreRequest with whitespace-only start page."""
        request = ExploreRequest(start_page="   ")

        assert request.validate() is False


class TestWikipediaPage:
    """Unit tests for WikipediaPage model."""

    def test_valid_wikipedia_page(self):
        """Test creating a valid WikipediaPage."""
        page = WikipediaPage(
            title="Test Page",
            page_id=12345,
            last_modified="2025-01-01T00:00:00Z",
            links=["Link 1", "Link 2"],
        )

        assert page.title == "Test Page"
        assert page.page_id == 12345
        assert page.last_modified == "2025-01-01T00:00:00Z"
        assert page.links == ["Link 1", "Link 2"]
        assert page.is_valid is True

    def test_wikipedia_page_minimal(self):
        """Test WikipediaPage with minimal required fields."""
        page = WikipediaPage(title="Test Page")

        assert page.title == "Test Page"
        assert page.page_id is None
        assert page.last_modified is None
        assert page.links is None
        assert page.is_valid is True

    def test_invalid_wikipedia_page_empty_title(self):
        """Test WikipediaPage with empty title."""
        page = WikipediaPage(title="")

        assert page.is_valid is False

    def test_invalid_wikipedia_page_whitespace_title(self):
        """Test WikipediaPage with whitespace-only title."""
        page = WikipediaPage(title="   ")

        assert page.is_valid is False


class TestTaskInfo:
    """Unit tests for TaskInfo model."""

    def test_task_info_creation(self):
        """Test creating a TaskInfo."""
        task_info = TaskInfo(
            task_id="test-task-123",
            status=TaskStatus.IN_PROGRESS,
            result={"path": ["A", "B"]},
            error=None,
            progress={"current": 50, "total": 100},
            created_at="2025-01-01T00:00:00Z",
            updated_at="2025-01-01T00:01:00Z",
        )

        assert task_info.task_id == "test-task-123"
        assert task_info.status == TaskStatus.IN_PROGRESS
        assert task_info.result == {"path": ["A", "B"]}
        assert task_info.error is None
        assert task_info.progress == {"current": 50, "total": 100}

    def test_task_info_minimal(self):
        """Test TaskInfo with minimal required fields."""
        task_info = TaskInfo(task_id="test-task-123", status=TaskStatus.PENDING)

        assert task_info.task_id == "test-task-123"
        assert task_info.status == TaskStatus.PENDING
        assert task_info.result is None
        assert task_info.error is None


class TestTaskStatus:
    """Unit tests for TaskStatus enum."""

    def test_task_status_values(self):
        """Test TaskStatus enum values."""
        assert TaskStatus.PENDING.value == "PENDING"
        assert TaskStatus.IN_PROGRESS.value == "IN_PROGRESS"
        assert TaskStatus.SUCCESS.value == "SUCCESS"
        assert TaskStatus.FAILURE.value == "FAILURE"
        assert TaskStatus.RETRY.value == "RETRY"

    def test_task_status_comparison(self):
        """Test TaskStatus enum comparison."""
        assert TaskStatus.PENDING == TaskStatus.PENDING
        assert TaskStatus.PENDING != TaskStatus.SUCCESS


class TestCacheStats:
    """Unit tests for CacheStats model."""

    def test_cache_stats_creation(self):
        """Test creating CacheStats."""
        stats = CacheStats(
            total_keys=1000, memory_usage=50000000, hit_rate=0.85, miss_rate=0.15
        )

        assert stats.total_keys == 1000
        assert stats.memory_usage == 50000000
        assert stats.hit_rate == 0.85
        assert stats.miss_rate == 0.15

    def test_cache_stats_minimal(self):
        """Test CacheStats with minimal required fields."""
        stats = CacheStats(total_keys=500)

        assert stats.total_keys == 500
        assert stats.memory_usage is None
        assert stats.hit_rate is None
        assert stats.miss_rate is None


class TestHealthStatus:
    """Unit tests for HealthStatus model."""

    def test_health_status_creation(self):
        """Test creating HealthStatus."""
        health = HealthStatus(
            status="healthy",
            redis_status="healthy",
            celery_status="healthy",
            wikipedia_api_status="healthy",
            timestamp="2025-01-01T00:00:00Z",
            details={"uptime": "24h"},
        )

        assert health.status == "healthy"
        assert health.redis_status == "healthy"
        assert health.celery_status == "healthy"
        assert health.wikipedia_api_status == "healthy"
        assert health.timestamp == "2025-01-01T00:00:00Z"
        assert health.details == {"uptime": "24h"}

    def test_health_status_minimal(self):
        """Test HealthStatus with minimal required fields."""
        health = HealthStatus(
            status="degraded",
            redis_status="unhealthy",
            celery_status="healthy",
            wikipedia_api_status="healthy",
            timestamp="2025-01-01T00:00:00Z",
        )

        assert health.status == "degraded"
        assert health.details is None
