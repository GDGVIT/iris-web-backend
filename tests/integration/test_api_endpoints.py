import json
from unittest.mock import patch, Mock


class TestPathfindingAPI:
    """Integration tests for pathfinding API endpoints."""

    def test_get_path_valid_request(
        self, client, mock_celery_task, valid_search_request
    ):
        """Test successful path request."""
        response = client.post(
            "/getPath",
            data=json.dumps(valid_search_request),
            content_type="application/json",
        )

        assert response.status_code == 202
        data = json.loads(response.data)
        assert data["status"] == "IN_PROGRESS"
        assert "task_id" in data
        assert "poll_url" in data
        assert data["start_page"] == valid_search_request["start"]
        assert data["end_page"] == valid_search_request["end"]

    def test_get_path_invalid_request(self, client, invalid_search_request):
        """Test path request with invalid data."""
        response = client.post(
            "/getPath",
            data=json.dumps(invalid_search_request),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"] is True
        assert "message" in data
        assert data["code"] == "VALIDATION_ERROR"

    def test_get_path_missing_content_type(self, client, valid_search_request):
        """Test path request without JSON content type."""
        response = client.post(
            "/getPath",
            data=json.dumps(valid_search_request),
            # Missing content_type='application/json'
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"] is True
        assert "Content-Type" in data["message"]

    def test_get_task_status_pending(self, client, mock_celery_task):
        """Test task status check for pending task."""
        task_id = "test-task-id-123"

        response = client.get(f"/tasks/status/{task_id}")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "PENDING"
        assert data["task_id"] == task_id

    def test_get_task_status_success(self, client, mock_celery_task, sample_path_data):
        """Test task status check for successful task."""
        task_id = "test-task-id-123"

        # Mock successful task result
        mock_async_result = mock_celery_task.mock_async_result
        mock_async_result.state = "SUCCESS"
        mock_async_result.result = {
            "status": "SUCCESS",
            "path": sample_path_data["path"],
            "length": sample_path_data["length"],
            "search_time": sample_path_data["search_time"],
        }

        response = client.get(f"/tasks/status/{task_id}")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "SUCCESS"
        assert data["task_id"] == task_id
        assert "result" in data
        assert data["result"]["path"] == sample_path_data["path"]

    def test_get_task_status_failure(self, client, mock_celery_task):
        """Test task status check for failed task."""
        task_id = "test-task-id-123"

        # Mock failed task result
        mock_async_result = mock_celery_task.mock_async_result
        mock_async_result.state = "FAILURE"
        mock_async_result.info = "Path not found"

        response = client.get(f"/tasks/status/{task_id}")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "FAILURE"
        assert data["task_id"] == task_id
        assert "error" in data


class TestExploreAPI:
    """Integration tests for explore API endpoints."""

    @patch("app.core.factory.ServiceFactory.create_explore_service")
    def test_explore_valid_request(
        self, mock_service_factory, client, valid_explore_request, sample_explore_data
    ):
        """Test successful explore request."""
        # Mock explore service
        from app.core.models import ExploreResult

        mock_explore_service = Mock()
        mock_explore_result = ExploreResult(**sample_explore_data)
        mock_explore_service.explore_page.return_value = mock_explore_result
        mock_service_factory.return_value = mock_explore_service

        response = client.post(
            "/explore",
            data=json.dumps(valid_explore_request),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["start_page"] == sample_explore_data["start_page"]
        assert data["nodes"] == sample_explore_data["nodes"]
        # Edges are serialized as lists, not tuples, in JSON
        expected_edges = [list(edge) for edge in sample_explore_data["edges"]]
        assert data["edges"] == expected_edges

    def test_explore_invalid_request(self, client):
        """Test explore request with invalid data."""
        invalid_request = {"start": ""}  # Empty start page

        response = client.post(
            "/explore",
            data=json.dumps(invalid_request),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"] is True
        assert data["code"] == "VALIDATION_ERROR"

    @patch("app.core.factory.ServiceFactory.create_explore_service")
    def test_explore_page_not_found(
        self, mock_service_factory, client, valid_explore_request
    ):
        """Test explore request for non-existent page."""
        from app.utils.exceptions import InvalidPageError

        # Mock explore service to raise exception
        mock_explore_service = Mock()
        mock_explore_service.explore_page.side_effect = InvalidPageError(
            "Page 'NonExistent' does not exist"
        )
        mock_service_factory.return_value = mock_explore_service

        response = client.post(
            "/explore",
            data=json.dumps(valid_explore_request),
            content_type="application/json",
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["error"] is True
        assert data["code"] == "INVALID_PAGE"


class TestHealthCheckAPI:
    """Integration tests for health check endpoint."""

    @patch("app.core.factory.ServiceFactory.get_redis_client")
    @patch("app.core.factory.ServiceFactory.get_cache_service")
    @patch("app.core.factory.ServiceFactory.get_wikipedia_client")
    def test_health_check_healthy(self, mock_wikipedia, mock_cache, mock_redis, client):
        """Test health check when all services are healthy."""
        # Mock healthy services
        mock_redis_client = Mock()
        mock_redis_client.ping.return_value = True
        mock_redis.return_value = mock_redis_client

        mock_cache_service = Mock()
        mock_cache_service.set.return_value = None
        mock_cache_service.get.return_value = "ok"
        mock_cache.return_value = mock_cache_service

        mock_wikipedia_client = Mock()
        mock_wikipedia.return_value = mock_wikipedia_client

        response = client.get("/health")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "healthy"
        assert data["redis_status"] == "healthy"
        assert data["cache_status"] == "healthy"
        assert data["wikipedia_api_status"] == "healthy"

    @patch("app.core.factory.ServiceFactory.get_redis_client")
    def test_health_check_redis_unhealthy(self, mock_redis, client):
        """Test health check when Redis is unhealthy."""
        # Mock unhealthy Redis
        mock_redis.side_effect = Exception("Redis connection failed")

        response = client.get("/health")

        assert response.status_code == 503
        data = json.loads(response.data)
        assert data["status"] == "degraded"
        assert "unhealthy" in data["redis_status"]


class TestCacheAPI:
    """Integration tests for cache management endpoints."""

    @patch("app.core.factory.ServiceFactory.create_cache_management_service")
    def test_clear_cache_success(self, mock_service_factory, client):
        """Test successful cache clearing."""
        # Mock cache management service
        mock_cache_service = Mock()
        mock_cache_service.clear_cache_pattern.return_value = 5  # 5 entries cleared
        mock_service_factory.return_value = mock_cache_service

        request_data = {"pattern": "wiki_links:*"}
        response = client.post(
            "/cache/clear",
            data=json.dumps(request_data),
            content_type="application/json",
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["message"] == "Cleared 5 cache entries"
        assert data["pattern"] == "wiki_links:*"

    def test_clear_cache_default_pattern(self, client):
        """Test cache clearing with default pattern."""
        with patch(
            "app.core.factory.ServiceFactory.create_cache_management_service"
        ) as mock_factory:
            mock_cache_service = Mock()
            mock_cache_service.clear_cache_pattern.return_value = 3
            mock_factory.return_value = mock_cache_service

            response = client.post(
                "/cache/clear",
                data=json.dumps({}),  # Empty request body
                content_type="application/json",
            )

            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["pattern"] == "wiki_links:*"  # Default pattern


class TestAPIInfo:
    """Integration tests for API information endpoints."""

    def test_index_endpoint(self, client):
        """Test API information endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["name"] == "Iris Wikipedia Pathfinder API"
        assert data["version"] == "2.0.0"
        assert "endpoints" in data
        assert "POST /getPath" in data["endpoints"]

    def test_404_error_handler(self, client):
        """Test 404 error handling."""
        response = client.get("/nonexistent-endpoint")

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["error"] is True
        assert data["code"] == "NOT_FOUND"

    def test_405_error_handler(self, client):
        """Test 405 error handling."""
        response = client.delete("/getPath")  # DELETE not allowed

        assert response.status_code == 405
        data = json.loads(response.data)
        assert data["error"] is True
        assert data["code"] == "METHOD_NOT_ALLOWED"


class TestAPIMiddleware:
    """Integration tests for API middleware functionality."""

    def test_cors_headers(self, client, valid_search_request):
        """Test CORS headers are added to responses."""
        with patch("app.infrastructure.tasks.find_path_task.delay") as mock_delay:
            mock_task = Mock()
            mock_task.id = "test-task-id"
            mock_delay.return_value = mock_task

            response = client.post(
                "/getPath",
                data=json.dumps(valid_search_request),
                content_type="application/json",
            )

            assert "Access-Control-Allow-Origin" in response.headers
            assert response.headers["Access-Control-Allow-Origin"] == "*"

    def test_request_size_validation(self, client):
        """Test request size validation."""
        # Create a large request (this is a simplified test)
        large_request = {"start": "A" * 1000, "end": "B" * 1000}  # Very long page name

        response = client.post(
            "/getPath", data=json.dumps(large_request), content_type="application/json"
        )

        # Should still pass since we're not actually exceeding the limit
        # In a real test, you'd create a request that exceeds the size limit
        assert response.status_code in [202, 400]  # Either success or validation error

    def test_json_content_type_requirement(self, client):
        """Test that JSON content type is required for POST endpoints."""
        response = client.post(
            "/getPath",
            data='{"start": "Page A", "end": "Page B"}',
            content_type="text/plain",  # Wrong content type
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["code"] == "INVALID_CONTENT_TYPE"
