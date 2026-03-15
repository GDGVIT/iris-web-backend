from unittest.mock import Mock

import pytest

from app.core.models import PathResult, SearchRequest
from app.core.services import (
    CacheManagementService,
    PathFindingService,
    WikipediaService,
)
from app.utils.exceptions import (
    DisambiguationPageError,
    InvalidPageError,
    PathNotFoundError,
)


class TestPathFindingService:
    """Integration tests for PathFindingService."""

    def test_find_path_success(
        self, mock_wikipedia_client, mock_cache_service, mock_path_finder
    ):
        service = PathFindingService(
            mock_path_finder, mock_cache_service, mock_wikipedia_client
        )
        request = SearchRequest(start_page="Page A", end_page="Page C")

        result = service.find_path(request)

        assert isinstance(result, PathResult)
        assert result.path == ["Page A", "Page B", "Page C"]
        assert result.length == 3
        assert result.start_page == "Page A"
        assert result.end_page == "Page C"
        assert result.search_time is not None

    def test_find_path_cached_result(
        self, mock_wikipedia_client, mock_cache_service, mock_path_finder
    ):
        """When a cached result exists, the path finder is not invoked."""
        cached_data = {
            "path": ["Page A", "Page B", "Page C"],
            "length": 3,
            "start_page": "Page A",
            "end_page": "Page C",
            "search_time": 1.5,
            "nodes_explored": 10,
        }
        cache_key = "path:Page A:Page C"
        mock_cache_service.get.side_effect = lambda key: (
            cached_data if key == cache_key else None
        )

        service = PathFindingService(
            mock_path_finder, mock_cache_service, mock_wikipedia_client
        )
        result = service.find_path(
            SearchRequest(start_page="Page A", end_page="Page C")
        )

        assert isinstance(result, PathResult)
        assert result.path == cached_data["path"]
        mock_path_finder.find_path.assert_not_called()

    def test_find_path_result_is_cached(
        self, mock_wikipedia_client, mock_cache_service, mock_path_finder
    ):
        """A successful find_path result is written to the cache."""
        service = PathFindingService(
            mock_path_finder, mock_cache_service, mock_wikipedia_client
        )
        service.find_path(SearchRequest(start_page="Page A", end_page="Page C"))

        mock_cache_service.set.assert_called_once()
        call_key = mock_cache_service.set.call_args[0][0]
        assert call_key == "path:Page A:Page C"

    def test_find_path_invalid_request(
        self, mock_wikipedia_client, mock_cache_service, mock_path_finder
    ):
        """Invalid SearchRequest raises InvalidPageError before path_finder is called."""
        service = PathFindingService(
            mock_path_finder, mock_cache_service, mock_wikipedia_client
        )
        request = SearchRequest(start_page="", end_page="Page C")

        with pytest.raises(InvalidPageError):
            service.find_path(request)

        mock_path_finder.find_path.assert_not_called()

    def test_find_path_not_found(
        self, mock_wikipedia_client, mock_cache_service, mock_path_finder
    ):
        """PathNotFoundError from the path finder propagates unchanged."""
        mock_path_finder.find_path.side_effect = PathNotFoundError("Page A", "Page C")
        service = PathFindingService(
            mock_path_finder, mock_cache_service, mock_wikipedia_client
        )

        with pytest.raises(PathNotFoundError):
            service.find_path(SearchRequest(start_page="Page A", end_page="Page C"))

    def test_validate_pages(
        self, mock_wikipedia_client, mock_cache_service, mock_path_finder
    ):
        """Both pages existing → (True, True, details); missing end → (True, False, ...)."""

        def mock_get_page_info(page):
            return {
                "exists": page != "NonExistent",
                "final_title": page,
                "was_redirected": False,
                "is_disambiguation": False,
            }

        mock_wikipedia_client.get_page_with_redirect_info.side_effect = (
            mock_get_page_info
        )

        service = PathFindingService(
            mock_path_finder, mock_cache_service, mock_wikipedia_client
        )

        # Test both pages exist
        start_exists, end_exists, validation_details = service.validate_pages(
            "Page A", "Page B"
        )
        assert start_exists is True
        assert end_exists is True
        assert validation_details["start_page"]["exists"] is True
        assert validation_details["end_page"]["exists"] is True

        # Test one page doesn't exist
        start_exists, end_exists, validation_details = service.validate_pages(
            "Page A", "NonExistent"
        )
        assert start_exists is True
        assert end_exists is False
        assert validation_details["start_page"]["exists"] is True
        assert validation_details["end_page"]["exists"] is False


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
        # The cache key is page_info:page_title
        cache_key = "page_info:Test Page"
        mock_cache_service.get.side_effect = lambda key: (
            cached_data if key == cache_key else None
        )

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


class TestValidatePagesDisambiguation:
    """Tests for disambiguation handling in validate_pages."""

    def test_disambiguation_end_page_raises(
        self, mock_wikipedia_client, mock_cache_service, mock_path_finder
    ):
        mock_wikipedia_client.get_page_with_redirect_info.side_effect = lambda page: {
            "exists": True,
            "final_title": page,
            "was_redirected": False,
            "is_disambiguation": page == "Mercury",
        }
        service = PathFindingService(
            mock_path_finder, mock_cache_service, mock_wikipedia_client
        )
        with pytest.raises(DisambiguationPageError):
            service.validate_pages("A", "Mercury")

    def test_disambiguation_start_page_is_allowed(
        self, mock_wikipedia_client, mock_cache_service, mock_path_finder
    ):
        """Disambiguation start pages do not raise — the user navigates from them."""
        mock_wikipedia_client.get_page_with_redirect_info.side_effect = lambda page: {
            "exists": True,
            "final_title": page,
            "was_redirected": False,
            "is_disambiguation": page == "Mercury",
        }
        service = PathFindingService(
            mock_path_finder, mock_cache_service, mock_wikipedia_client
        )
        start_exists, end_exists, details = service.validate_pages("Mercury", "Target")
        assert start_exists is True
        assert end_exists is True
        assert details["start_page"]["is_disambiguation"] is True

    def test_validate_returns_redirect_info(
        self, mock_wikipedia_client, mock_cache_service, mock_path_finder
    ):
        """Redirect metadata is surfaced in validation_details."""
        mock_wikipedia_client.get_page_with_redirect_info.side_effect = lambda page: {
            "exists": True,
            "final_title": "AI" if page == "Artificial intelligence" else page,
            "was_redirected": page == "Artificial intelligence",
            "is_disambiguation": False,
        }
        service = PathFindingService(
            mock_path_finder, mock_cache_service, mock_wikipedia_client
        )
        _, _, details = service.validate_pages("Artificial intelligence", "Python")
        assert details["start_page"]["was_redirected"] is True


class TestCacheManagementService:
    def test_clear_pattern_success(self):
        cache = Mock()
        cache.clear_pattern.return_value = 5
        svc = CacheManagementService(cache)
        assert svc.clear_cache_pattern("wiki_*") == 5

    def test_clear_pattern_exception_returns_zero(self):
        cache = Mock()
        cache.clear_pattern.side_effect = Exception("redis down")
        svc = CacheManagementService(cache)
        assert svc.clear_cache_pattern("wiki_*") == 0

    def test_get_cache_stats(self):
        svc = CacheManagementService(Mock())
        stats = svc.get_cache_stats()
        assert stats["status"] == "available"


class TestWikipediaServiceCacheHit:
    def test_get_page_info_cache_hit(self, mock_wikipedia_client, mock_cache_service):
        cached = {"title": "Python", "page_id": 42, "last_modified": "2025"}
        mock_cache_service.set("page_info:Python", cached)

        svc = WikipediaService(mock_wikipedia_client, mock_cache_service)
        result = svc.get_page_info("Python")

        assert result is not None
        assert result.title == "Python"
        mock_wikipedia_client.get_page_info.assert_not_called()

    def test_get_page_info_not_found_returns_none(
        self, mock_wikipedia_client, mock_cache_service
    ):
        mock_wikipedia_client.get_page_info.return_value = None
        svc = WikipediaService(mock_wikipedia_client, mock_cache_service)
        assert svc.get_page_info("Ghost") is None
