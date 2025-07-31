import pytest
from unittest.mock import Mock, patch
from app.core.services import PathFindingService, ExploreService, WikipediaService
from app.core.models import SearchRequest, ExploreRequest, PathResult, ExploreResult
from app.utils.exceptions import PathNotFoundError, InvalidPageError


class TestPathFindingService:
    """Integration tests for PathFindingService."""

    def test_find_path_success(self, mock_wikipedia_client, mock_cache_service):
        """Test successful pathfinding."""
        # Mock path finder
        mock_path_finder = Mock()
        mock_path_finder.find_shortest_path.return_value = {
            "path": ["Page A", "Page B", "Page C"],
            "nodes_explored": 10,
        }

        # Create service
        service = PathFindingService(
            mock_path_finder, mock_cache_service, mock_wikipedia_client
        )

        # Create request
        request = SearchRequest(start_page="Page A", end_page="Page C")

        # Execute
        result = service.find_path(request)

        # Assert
        assert isinstance(result, PathResult)
        assert result.path == ["Page A", "Page B", "Page C"]
        assert result.length == 3
        assert result.start_page == "Page A"
        assert result.end_page == "Page C"
        assert result.search_time is not None

    def test_find_path_cached_result(self, mock_wikipedia_client, mock_cache_service):
        """Test pathfinding with cached result."""
        # Mock cached result
        cached_data = {
            "path": ["Page A", "Page B", "Page C"],
            "length": 3,
            "start_page": "Page A",
            "end_page": "Page C",
            "search_time": 1.5,
        }
        mock_cache_service.get.return_value = cached_data

        # Mock path finder (should not be called)
        mock_path_finder = Mock()

        # Create service
        service = PathFindingService(
            mock_path_finder, mock_cache_service, mock_wikipedia_client
        )

        # Create request
        request = SearchRequest(start_page="Page A", end_page="Page C")

        # Execute
        result = service.find_path(request)

        # Assert
        assert isinstance(result, PathResult)
        assert result.path == cached_data["path"]
        mock_path_finder.find_shortest_path.assert_not_called()

    def test_find_path_invalid_request(self, mock_wikipedia_client, mock_cache_service):
        """Test pathfinding with invalid request."""
        mock_path_finder = Mock()
        service = PathFindingService(
            mock_path_finder, mock_cache_service, mock_wikipedia_client
        )

        # Invalid request (empty start page)
        request = SearchRequest(start_page="", end_page="Page C")

        with pytest.raises(InvalidPageError):
            service.find_path(request)

    def test_find_path_not_found(self, mock_wikipedia_client, mock_cache_service):
        """Test pathfinding when no path exists."""
        # Mock path finder to raise PathNotFoundError
        mock_path_finder = Mock()
        mock_path_finder.find_shortest_path.side_effect = PathNotFoundError(
            "Page A", "Page C"
        )

        service = PathFindingService(
            mock_path_finder, mock_cache_service, mock_wikipedia_client
        )

        request = SearchRequest(start_page="Page A", end_page="Page C")

        with pytest.raises(PathNotFoundError):
            service.find_path(request)

    def test_validate_pages(self, mock_wikipedia_client, mock_cache_service):
        """Test page validation."""
        # Mock Wikipedia client responses
        mock_wikipedia_client.page_exists.side_effect = (
            lambda page: page != "NonExistent"
        )

        mock_path_finder = Mock()
        service = PathFindingService(
            mock_path_finder, mock_cache_service, mock_wikipedia_client
        )

        # Test both pages exist
        start_exists, end_exists = service.validate_pages("Page A", "Page B")
        assert start_exists is True
        assert end_exists is True

        # Test one page doesn't exist
        start_exists, end_exists = service.validate_pages("Page A", "NonExistent")
        assert start_exists is True
        assert end_exists is False


class TestExploreService:
    """Integration tests for ExploreService."""

    def test_explore_page_success(self, mock_wikipedia_client, mock_cache_service):
        """Test successful page exploration."""
        # Mock Wikipedia client
        mock_wikipedia_client.page_exists.return_value = True
        mock_wikipedia_client.get_links_bulk.return_value = {
            "Test Page": ["Link 1", "Link 2", "Link 3", "Link 4", "Link 5"]
        }

        # Create service
        service = ExploreService(mock_wikipedia_client, mock_cache_service)

        # Create request
        request = ExploreRequest(start_page="Test Page", max_links=3)

        # Execute
        result = service.explore_page(request)

        # Assert
        assert isinstance(result, ExploreResult)
        assert result.start_page == "Test Page"
        assert len(result.nodes) == 4  # Start page + 3 links
        assert len(result.edges) == 3  # 3 connections
        assert result.total_links == 5  # Total available links

    def test_explore_page_cached_result(
        self, mock_wikipedia_client, mock_cache_service
    ):
        """Test page exploration with cached result."""
        # Mock cached result
        cached_data = {
            "start_page": "Test Page",
            "nodes": ["Test Page", "Link 1", "Link 2"],
            "edges": [("Test Page", "Link 1"), ("Test Page", "Link 2")],
            "total_links": 2,
        }
        mock_cache_service.get.return_value = cached_data

        # Create service
        service = ExploreService(mock_wikipedia_client, mock_cache_service)

        # Create request
        request = ExploreRequest(start_page="Test Page")

        # Execute
        result = service.explore_page(request)

        # Assert
        assert isinstance(result, ExploreResult)
        assert result.start_page == cached_data["start_page"]
        mock_wikipedia_client.get_links_bulk.assert_not_called()

    def test_explore_page_not_found(self, mock_wikipedia_client, mock_cache_service):
        """Test exploration of non-existent page."""
        # Mock page doesn't exist
        mock_wikipedia_client.page_exists.return_value = False

        service = ExploreService(mock_wikipedia_client, mock_cache_service)
        request = ExploreRequest(start_page="NonExistent")

        with pytest.raises(InvalidPageError):
            service.explore_page(request)

    def test_explore_page_no_links(self, mock_wikipedia_client, mock_cache_service):
        """Test exploration of page with no links."""
        # Mock page exists but has no links
        mock_wikipedia_client.page_exists.return_value = True
        mock_wikipedia_client.get_links_bulk.return_value = {"Test Page": []}

        service = ExploreService(mock_wikipedia_client, mock_cache_service)
        request = ExploreRequest(start_page="Test Page")

        result = service.explore_page(request)

        assert isinstance(result, ExploreResult)
        assert result.start_page == "Test Page"
        assert result.nodes == ["Test Page"]
        assert result.edges == []
        assert result.total_links == 0

    def test_explore_invalid_request(self, mock_wikipedia_client, mock_cache_service):
        """Test exploration with invalid request."""
        service = ExploreService(mock_wikipedia_client, mock_cache_service)

        # Invalid request (empty start page)
        request = ExploreRequest(start_page="")

        with pytest.raises(InvalidPageError):
            service.explore_page(request)


class TestWikipediaService:
    """Integration tests for WikipediaService."""

    def test_get_page_info_success(self, mock_wikipedia_client, mock_cache_service):
        """Test successful page info retrieval."""
        # Mock Wikipedia client
        page_info_data = {
            "title": "Test Page",
            "page_id": 12345,
            "last_modified": "2025-01-01T00:00:00Z",
        }
        mock_wikipedia_client.get_page_info.return_value = page_info_data

        # Create service
        service = WikipediaService(mock_wikipedia_client, mock_cache_service)

        # Execute
        result = service.get_page_info("Test Page")

        # Assert
        assert result is not None
        assert result.title == "Test Page"
        assert result.page_id == 12345
        assert result.last_modified == "2025-01-01T00:00:00Z"

    def test_get_page_info_cached(self, mock_wikipedia_client, mock_cache_service):
        """Test page info retrieval with cached result."""
        # Mock cached result
        cached_data = {
            "title": "Test Page",
            "page_id": 12345,
            "last_modified": "2025-01-01T00:00:00Z",
            "links": None,
        }
        mock_cache_service.get.return_value = cached_data

        service = WikipediaService(mock_wikipedia_client, mock_cache_service)
        result = service.get_page_info("Test Page")

        assert result is not None
        assert result.title == "Test Page"
        mock_wikipedia_client.get_page_info.assert_not_called()

    def test_get_page_info_not_found(self, mock_wikipedia_client, mock_cache_service):
        """Test page info retrieval for non-existent page."""
        # Mock page doesn't exist
        mock_wikipedia_client.get_page_info.return_value = None

        service = WikipediaService(mock_wikipedia_client, mock_cache_service)
        result = service.get_page_info("NonExistent")

        assert result is None

    def test_get_page_info_invalid_title(
        self, mock_wikipedia_client, mock_cache_service
    ):
        """Test page info retrieval with invalid title."""
        service = WikipediaService(mock_wikipedia_client, mock_cache_service)

        with pytest.raises(InvalidPageError):
            service.get_page_info("")  # Empty title

    def test_search_pages(self, mock_wikipedia_client, mock_cache_service):
        """Test page search functionality."""
        service = WikipediaService(mock_wikipedia_client, mock_cache_service)

        # Current implementation returns empty list
        result = service.search_pages("python programming")
        assert result == []


class TestServiceIntegration:
    """Integration tests combining multiple services."""

    @patch("app.core.factory.ServiceFactory")
    def test_pathfinding_with_explore_validation(
        self,
        mock_factory,
        mock_wikipedia_client,
        mock_cache_service,
        mock_queue_service,
    ):
        """Test pathfinding after validating pages exist through explore."""
        # Setup mocks
        mock_path_finder = Mock()
        mock_path_finder.find_shortest_path.return_value = {
            "path": ["Page A", "Page B", "Page C"],
            "nodes_explored": 10,
        }

        # Mock page exists and has links
        mock_wikipedia_client.page_exists.return_value = True
        mock_wikipedia_client.get_links_bulk.return_value = {
            "Page A": ["Page B", "Page C"]
        }

        # Create services
        path_service = PathFindingService(
            mock_path_finder, mock_cache_service, mock_wikipedia_client
        )
        explore_service = ExploreService(mock_wikipedia_client, mock_cache_service)

        # First, explore the starting page to validate it exists
        explore_request = ExploreRequest(start_page="Page A", max_links=5)
        explore_result = explore_service.explore_page(explore_request)

        assert explore_result.start_page == "Page A"
        assert len(explore_result.nodes) > 1  # Has links

        # Then find path
        search_request = SearchRequest(start_page="Page A", end_page="Page C")
        path_result = path_service.find_path(search_request)

        assert path_result.path == ["Page A", "Page B", "Page C"]
        assert path_result.length == 3

    def test_service_error_propagation(self, mock_wikipedia_client, mock_cache_service):
        """Test that service errors are properly propagated."""
        # Mock Wikipedia client to raise exception
        mock_wikipedia_client.page_exists.side_effect = Exception("Wikipedia API error")

        service = ExploreService(mock_wikipedia_client, mock_cache_service)
        request = ExploreRequest(start_page="Test Page")

        with pytest.raises(Exception, match="Wikipedia API error"):
            service.explore_page(request)
