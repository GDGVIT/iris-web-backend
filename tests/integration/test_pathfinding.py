import pytest
from unittest.mock import Mock
from app.core.pathfinding import RedisBasedBFSPathFinder, BidirectionalBFSPathFinder
from app.utils.exceptions import PathNotFoundError, InvalidPageError


class TestRedisBasedBFSPathFinder:
    """Integration tests for Redis-based BFS pathfinding algorithm."""

    def test_find_shortest_path_direct_connection(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Test pathfinding with direct connection."""
        # Mock Wikipedia client - Page A links directly to Page B
        mock_wikipedia_client.page_exists.return_value = True
        mock_wikipedia_client.get_links_bulk.return_value = {
            "Page A": ["Page B", "Page C"]
        }

        # Create pathfinder
        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service, max_depth=3
        )

        # Execute
        result = pathfinder.find_shortest_path("Page A", "Page B")

        # Assert
        assert result["path"] == ["Page A", "Page B"]
        assert "nodes_explored" in result

    def test_find_shortest_path_two_hops(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Test pathfinding with two-hop path."""

        # Mock Wikipedia client responses for BFS levels
        def mock_get_links_bulk(pages):
            links_map = {
                "Page A": ["Page X", "Page Y"],
                "Page X": ["Page B", "Page Z"],
                "Page Y": ["Page Z"],
            }
            return {page: links_map.get(page, []) for page in pages}

        mock_wikipedia_client.page_exists.return_value = True
        mock_wikipedia_client.get_links_bulk.side_effect = mock_get_links_bulk

        # Create pathfinder
        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service, max_depth=3
        )

        # Execute
        result = pathfinder.find_shortest_path("Page A", "Page B")

        # Assert
        assert result["path"] == ["Page A", "Page X", "Page B"]
        assert "nodes_explored" in result

    def test_find_shortest_path_same_page(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Test pathfinding when start and end are the same."""
        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        result = pathfinder.find_shortest_path("Page A", "Page A")
        assert result["path"] == ["Page A"]
        assert result["nodes_explored"] == 1

    def test_find_shortest_path_invalid_pages(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Test pathfinding with invalid page inputs."""
        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        # Empty start page
        with pytest.raises(InvalidPageError):
            pathfinder.find_shortest_path("", "Page B")

        # Empty end page
        with pytest.raises(InvalidPageError):
            pathfinder.find_shortest_path("Page A", "")

    def test_find_shortest_path_nonexistent_start_page(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Test pathfinding when start page doesn't exist."""
        # Mock start page doesn't exist
        mock_wikipedia_client.page_exists.side_effect = (
            lambda page: page != "NonExistent"
        )

        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        with pytest.raises(
            InvalidPageError, match="Start page 'NonExistent' does not exist"
        ):
            pathfinder.find_shortest_path("NonExistent", "Page B")

    def test_find_shortest_path_nonexistent_end_page(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Test pathfinding when end page doesn't exist."""
        # Mock end page doesn't exist
        mock_wikipedia_client.page_exists.side_effect = (
            lambda page: page != "NonExistent"
        )

        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        with pytest.raises(
            InvalidPageError, match="End page 'NonExistent' does not exist"
        ):
            pathfinder.find_shortest_path("Page A", "NonExistent")

    def test_find_shortest_path_no_path_exists(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Test pathfinding when no path exists between pages."""

        # Mock isolated pages - no connecting links
        def mock_get_links_bulk(pages):
            # Page A only links to Page X, Page B only links to Page Y (isolated)
            links_map = {
                "Page A": ["Page X"],
                "Page X": ["Page A"],  # Circular reference
                "Page B": ["Page Y"],
                "Page Y": ["Page B"],  # Circular reference
            }
            return {page: links_map.get(page, []) for page in pages}

        mock_wikipedia_client.page_exists.return_value = True
        mock_wikipedia_client.get_links_bulk.side_effect = mock_get_links_bulk

        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service, max_depth=2
        )

        with pytest.raises(PathNotFoundError):
            pathfinder.find_shortest_path("Page A", "Page B")

    def test_find_shortest_path_max_depth_reached(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Test pathfinding when maximum depth is reached."""

        # Mock a long chain of pages
        def mock_get_links_bulk(pages):
            links_map = {
                "Page A": ["Page 1"],
                "Page 1": ["Page 2"],
                "Page 2": ["Page 3"],
                "Page 3": ["Page 4"],
                "Page 4": ["Page B"],  # Path exists but requires depth > max_depth
            }
            return {page: links_map.get(page, []) for page in pages}

        mock_wikipedia_client.page_exists.return_value = True
        mock_wikipedia_client.get_links_bulk.side_effect = mock_get_links_bulk

        # Set low max depth
        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service, max_depth=2
        )

        with pytest.raises(PathNotFoundError):
            pathfinder.find_shortest_path("Page A", "Page B")

    def test_redis_queue_integration(self, mock_wikipedia_client, mock_cache_service):
        """Test that Redis queue operations work correctly."""
        # Use a real-like queue implementation for testing
        queue_data = {}

        def mock_push(queue_name, item):
            if queue_name not in queue_data:
                queue_data[queue_name] = []
            queue_data[queue_name].append(item)

        def mock_pop(queue_name):
            if queue_name in queue_data and queue_data[queue_name]:
                return queue_data[queue_name].pop(0)
            return None

        def mock_length(queue_name):
            return len(queue_data.get(queue_name, []))

        def mock_clear(queue_name):
            queue_data.pop(queue_name, None)

        def mock_push_batch(queue_name, items):
            if queue_name not in queue_data:
                queue_data[queue_name] = []
            queue_data[queue_name].extend(items)

        mock_queue_service = Mock()
        mock_queue_service.push.side_effect = mock_push
        mock_queue_service.pop.side_effect = mock_pop
        mock_queue_service.length.side_effect = mock_length
        mock_queue_service.clear.side_effect = mock_clear
        mock_queue_service.push_batch.side_effect = mock_push_batch

        # Mock simple path A -> B
        mock_wikipedia_client.page_exists.return_value = True
        mock_wikipedia_client.get_links_bulk.return_value = {"Page A": ["Page B"]}

        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        result = pathfinder.find_shortest_path("Page A", "Page B")

        assert result["path"] == ["Page A", "Page B"]
        assert "nodes_explored" in result
        # Verify queue operations were called
        assert mock_queue_service.push.called
        assert mock_queue_service.pop.called
        assert mock_queue_service.clear.called

    def test_cache_integration(self, mock_wikipedia_client, mock_queue_service):
        """Test that cache operations work correctly for visited pages and paths."""
        # Use a real-like cache implementation for testing
        cache_data = {}

        def mock_get(key):
            return cache_data.get(key)

        def mock_set(key, value, ttl=None):
            cache_data[key] = value

        def mock_exists(key):
            return key in cache_data

        mock_cache_service = Mock()
        mock_cache_service.get.side_effect = mock_get
        mock_cache_service.set.side_effect = mock_set
        mock_cache_service.exists.side_effect = mock_exists

        # Mock simple path A -> B
        mock_wikipedia_client.page_exists.return_value = True
        mock_wikipedia_client.get_links_bulk.return_value = {"Page A": ["Page B"]}

        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        result = pathfinder.find_shortest_path("Page A", "Page B")

        assert result["path"] == ["Page A", "Page B"]
        assert "nodes_explored" in result
        # Verify cache operations were called for visited tracking and path storage
        assert mock_cache_service.set.called
        assert mock_cache_service.get.called


class TestBidirectionalBFSPathFinder:
    """Integration tests for bidirectional BFS pathfinding."""

    def test_bidirectional_fallback_to_regular_bfs(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Test that bidirectional BFS falls back to regular BFS for now."""
        # Mock simple path
        mock_wikipedia_client.page_exists.return_value = True
        mock_wikipedia_client.get_links_bulk.return_value = {"Page A": ["Page B"]}

        pathfinder = BidirectionalBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        result = pathfinder.find_shortest_path("Page A", "Page B")

        # Should work through fallback mechanism
        assert result["path"] == ["Page A", "Page B"]
        assert "nodes_explored" in result


class TestPathfindingErrorHandling:
    """Integration tests for pathfinding error scenarios."""

    def test_wikipedia_api_error_handling(self, mock_cache_service, mock_queue_service):
        """Test handling of Wikipedia API errors."""
        from app.utils.exceptions import WikipediaAPIError

        # Mock Wikipedia client to raise API error
        mock_wikipedia_client = Mock()
        mock_wikipedia_client.page_exists.return_value = True
        mock_wikipedia_client.get_links_bulk.side_effect = WikipediaAPIError(
            "API request failed"
        )

        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        with pytest.raises(WikipediaAPIError):
            pathfinder.find_shortest_path("Page A", "Page B")

    def test_cache_error_handling(self, mock_wikipedia_client, mock_queue_service):
        """Test handling of cache errors."""
        from app.utils.exceptions import CacheConnectionError

        # Mock cache service to raise error
        mock_cache_service = Mock()
        mock_cache_service.exists.side_effect = CacheConnectionError(
            "Redis connection failed"
        )
        # Mock other cache methods to not raise errors so we reach the exists call
        mock_cache_service.get.return_value = [
            "Page A"
        ]  # Return a path for current page
        mock_cache_service.set.return_value = None

        mock_wikipedia_client.page_exists.return_value = True
        # Set up links that don't immediately lead to target, forcing visited check
        mock_wikipedia_client.get_links_bulk.return_value = {
            "Page A": ["Page C", "Page D"]
        }

        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        with pytest.raises(CacheConnectionError):
            pathfinder.find_shortest_path("Page A", "Page B")

    def test_queue_error_handling(self, mock_wikipedia_client, mock_cache_service):
        """Test handling of queue errors."""
        from app.utils.exceptions import CacheConnectionError

        # Mock queue service to raise error
        mock_queue_service = Mock()
        mock_queue_service.push.side_effect = CacheConnectionError(
            "Queue operation failed"
        )

        mock_wikipedia_client.page_exists.return_value = True

        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        with pytest.raises(CacheConnectionError):
            pathfinder.find_shortest_path("Page A", "Page B")
