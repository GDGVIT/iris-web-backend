import pytest
import os
from unittest.mock import Mock, patch
from app import create_app
from config.testing import TestingConfig
from app.core.factory import ServiceFactory


@pytest.fixture(scope="session")
def app():
    """Create application for testing."""
    # Use testing configuration
    app = create_app(TestingConfig)

    # Create application context
    with app.app_context():
        yield app


@pytest.fixture(scope="function")
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture(scope="function")
def mock_redis():
    """Mock Redis client for testing."""
    mock_redis = Mock()
    mock_redis.ping.return_value = True
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True
    mock_redis.setex.return_value = True
    mock_redis.delete.return_value = 1
    mock_redis.exists.return_value = False
    mock_redis.lpop.return_value = None
    mock_redis.rpush.return_value = 1
    mock_redis.llen.return_value = 0
    mock_redis.keys.return_value = []
    return mock_redis


@pytest.fixture(scope="function")
def mock_wikipedia_client():
    """Mock Wikipedia client for testing."""
    mock_client = Mock()
    mock_client.page_exists.return_value = True
    mock_client.get_links_bulk.return_value = {
        "Test Page 1": ["Test Page 2", "Test Page 3"],
        "Test Page 2": ["Test Page 3", "Test Page 4"],
        "Test Page 3": ["Test Page 4"],
    }
    mock_client.get_page_info.return_value = {
        "title": "Test Page",
        "page_id": 12345,
        "last_modified": "2025-01-01T00:00:00Z",
    }
    return mock_client


@pytest.fixture(scope="function")
def mock_cache_service():
    """Mock cache service for testing."""
    cache_data = {}

    mock_cache = Mock()

    def mock_get(key):
        return cache_data.get(key)

    def mock_set(key, value, ttl=None):
        cache_data[key] = value

    def mock_exists(key):
        return key in cache_data

    def mock_delete(key):
        cache_data.pop(key, None)

    mock_cache.get.side_effect = mock_get
    mock_cache.set.side_effect = mock_set
    mock_cache.exists.side_effect = mock_exists
    mock_cache.delete.side_effect = mock_delete

    return mock_cache


@pytest.fixture(scope="function")
def mock_queue_service():
    """Mock queue service for testing."""
    queues = {}

    mock_queue = Mock()

    def mock_push(queue_name, item):
        if queue_name not in queues:
            queues[queue_name] = []
        queues[queue_name].append(item)

    def mock_pop(queue_name):
        if queue_name in queues and queues[queue_name]:
            return queues[queue_name].pop(0)
        return None

    def mock_length(queue_name):
        return len(queues.get(queue_name, []))

    def mock_clear(queue_name):
        queues.pop(queue_name, None)

    def mock_push_batch(queue_name, items):
        if queue_name not in queues:
            queues[queue_name] = []
        queues[queue_name].extend(items)

    mock_queue.push.side_effect = mock_push
    mock_queue.pop.side_effect = mock_pop
    mock_queue.length.side_effect = mock_length
    mock_queue.clear.side_effect = mock_clear
    mock_queue.push_batch.side_effect = mock_push_batch

    return mock_queue


@pytest.fixture(scope="function")
def mock_celery_task():
    """Mock Celery task for testing."""
    mock_task = Mock()
    mock_task.id = "test-task-id-123"
    mock_task.state = "PENDING"
    mock_task.result = None
    mock_task.info = None

    # Mock AsyncResult - this will be the object returned by AsyncResult()
    mock_async_result = Mock()
    mock_async_result.state = "PENDING"
    mock_async_result.result = None
    mock_async_result.info = None

    with patch("app.api.routes.find_path_task") as mock_find_path_task:
        mock_find_path_task.delay.return_value = mock_task
        # Make AsyncResult callable and return the same mock instance each time
        mock_find_path_task.AsyncResult = Mock(return_value=mock_async_result)
        # Store the mock_async_result on the mock_find_path_task for test access
        mock_find_path_task.mock_async_result = mock_async_result
        yield mock_find_path_task


@pytest.fixture(scope="function", autouse=True)
def cleanup_services():
    """Clean up service factory after each test."""
    yield
    ServiceFactory.cleanup()


@pytest.fixture(scope="function")
def sample_path_data():
    """Sample path data for testing."""
    return {
        "path": ["Page A", "Page B", "Page C"],
        "length": 3,
        "start_page": "Page A",
        "end_page": "Page C",
        "search_time": 1.5,
        "nodes_explored": 10,
    }


@pytest.fixture(scope="function")
def sample_explore_data():
    """Sample explore data for testing."""
    return {
        "start_page": "Test Page",
        "nodes": ["Test Page", "Link 1", "Link 2", "Link 3"],
        "edges": [
            ("Test Page", "Link 1"),
            ("Test Page", "Link 2"),
            ("Test Page", "Link 3"),
        ],
        "total_links": 3,
    }


@pytest.fixture(scope="function")
def valid_search_request():
    """Valid search request data."""
    return {
        "start": "Python (programming language)",
        "end": "Machine learning",
        "algorithm": "bfs",
    }


@pytest.fixture(scope="function")
def valid_explore_request():
    """Valid explore request data."""
    return {"start": "Python (programming language)", "max_links": 10}


@pytest.fixture(scope="function")
def invalid_search_request():
    """Invalid search request data."""
    return {"start": "", "end": "Machine learning"}  # Empty start page


@pytest.fixture(scope="function")
def mock_successful_pathfinding():
    """Mock successful pathfinding operation."""

    def mock_find_path(start, end):
        return ["Python (programming language)", "Computer science", "Machine learning"]

    return mock_find_path


@pytest.fixture(scope="function")
def mock_failed_pathfinding():
    """Mock failed pathfinding operation."""

    def mock_find_path(start, end):
        from app.utils.exceptions import PathNotFoundError

        raise PathNotFoundError(start, end)

    return mock_find_path


# Environment setup
@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables."""
    os.environ["FLASK_ENV"] = "testing"
    os.environ["TESTING"] = "true"
    os.environ["REDIS_URL"] = "redis://localhost:6379/1"  # Use test database
    os.environ["SECRET_KEY"] = "test-secret-key"
    os.environ["LOG_LEVEL"] = "DEBUG"
    yield
    # Cleanup is handled by pytest
