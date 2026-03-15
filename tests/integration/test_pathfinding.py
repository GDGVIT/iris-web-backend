from unittest.mock import Mock

import pytest

from app.core.pathfinding import (
    BidirectionalBFSPathFinder,
    BidirProgressAggregator,
    RedisBasedBFSPathFinder,
)
from app.utils.exceptions import InvalidPageError, PathNotFoundError


class TestRedisBasedBFSPathFinder:
    """Integration tests for Redis-based BFS pathfinding algorithm."""

    def test_find_path_direct_connection(
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
        result = pathfinder.find_path("Page A", "Page B")

        # Assert
        assert result["path"] == ["Page A", "Page B"]
        assert "nodes_explored" in result

    def test_find_path_two_hops(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Test pathfinding with two-hop path."""

        # Mock Wikipedia client responses for BFS levels
        def mock_get_links_bulk(pages, on_page_fetched=None):
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
        result = pathfinder.find_path("Page A", "Page B")

        # Assert
        assert result["path"] == ["Page A", "Page X", "Page B"]
        assert "nodes_explored" in result

    def test_find_path_same_page(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Test pathfinding when start and end are the same."""
        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        result = pathfinder.find_path("Page A", "Page A")
        assert result["path"] == ["Page A"]
        assert result["nodes_explored"] == 1

    def test_find_path_invalid_pages(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Test pathfinding with invalid page inputs."""
        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        # Empty start page
        with pytest.raises(InvalidPageError):
            pathfinder.find_path("", "Page B")

        # Empty end page
        with pytest.raises(InvalidPageError):
            pathfinder.find_path("Page A", "")

    def test_find_path_no_path_exists(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Test pathfinding when no path exists between pages."""

        # Mock isolated pages - no connecting links
        def mock_get_links_bulk(pages, on_page_fetched=None):
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
            pathfinder.find_path("Page A", "Page B")

    def test_find_path_max_depth_reached(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Test pathfinding when maximum depth is reached."""

        # Mock a long chain of pages
        def mock_get_links_bulk(pages, on_page_fetched=None):
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
            pathfinder.find_path("Page A", "Page B")

    def test_redis_queue_integration(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Queue push and pop_batch are called during BFS (uses conftest fixture)."""
        mock_wikipedia_client.page_exists.return_value = True
        mock_wikipedia_client.get_links_bulk.return_value = {"Page A": ["Page B"]}

        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        result = pathfinder.find_path("Page A", "Page B")

        assert result["path"] == ["Page A", "Page B"]
        assert "nodes_explored" in result
        assert mock_queue_service.push.called
        assert mock_queue_service.pop_batch.called

    def test_redis_ops_integration(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Test that set/hash cache operations are used correctly for visited tracking."""
        mock_wikipedia_client.page_exists.return_value = True
        mock_wikipedia_client.get_links_bulk.return_value = {"Page A": ["Page B"]}

        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        result = pathfinder.find_path("Page A", "Page B")

        assert result["path"] == ["Page A", "Page B"]
        assert "nodes_explored" in result
        # Verify set/hash interface methods were used for visited tracking
        assert mock_cache_service.set_add.called
        assert mock_cache_service.hash_set.called


class TestProgressCallback:
    """Tests for progress callback invocation in RedisBasedBFSPathFinder."""

    def test_callback_fires_during_multi_hop_search(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Progress callback fires at least once during a non-trivial search."""
        progress_calls = []

        def mock_get_links(pages, on_page_fetched=None):
            mapping = {
                "Page A": ["Page X"],  # first batch: no direct path
                "Page X": ["Page B"],  # second batch: finds target
            }
            # Simulate Wikipedia client calling the per-page callback
            if on_page_fetched:
                for page in pages:
                    on_page_fetched(page, mapping.get(page, []))
            return {page: mapping.get(page, []) for page in pages}

        mock_wikipedia_client.get_links_bulk.side_effect = mock_get_links

        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client,
            mock_cache_service,
            mock_queue_service,
            progress_callback=lambda data: progress_calls.append(data),
        )

        result = pathfinder.find_path("Page A", "Page B")

        assert result["path"] == ["Page A", "Page X", "Page B"]
        assert len(progress_calls) > 0
        for call in progress_calls:
            assert "search_stats" in call
            assert "nodes_explored" in call["search_stats"]

    def test_no_callback_does_not_raise(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Pathfinder with no callback runs without error."""
        mock_wikipedia_client.get_links_bulk.return_value = {"Page A": ["Page B"]}

        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client,
            mock_cache_service,
            mock_queue_service,
            progress_callback=None,
        )

        result = pathfinder.find_path("Page A", "Page B")
        assert result["path"] == ["Page A", "Page B"]


class TestBidirProgressAggregator:
    """Unit tests for BidirProgressAggregator."""

    def _make_agg(self, callback=None):
        queue_svc = Mock()
        queue_svc.length.return_value = 0
        return BidirProgressAggregator(callback or Mock(), queue_svc, "fwd_q", "bwd_q")

    def test_forward_and_backward_counting(self):
        agg = self._make_agg()
        agg.record("A", 0, "forward")
        agg.record("B", 1, "backward")
        agg.record("C", 1, "forward")

        assert agg.total_nodes == 3
        assert agg._fwd_nodes == 2
        assert agg._bwd_nodes == 1

    def test_total_nodes_starts_at_zero(self):
        agg = self._make_agg()
        assert agg.total_nodes == 0

    def test_callback_receives_combined_queue_size(self):
        received = []
        queue_svc = Mock()
        queue_svc.length.side_effect = lambda q: 3 if q == "fwd_q" else 2

        agg = BidirProgressAggregator(received.append, queue_svc, "fwd_q", "bwd_q")
        agg.record("Page A", 0, "forward")

        assert len(received) == 1
        update = received[0]
        assert update["nodes_explored"] == 1
        assert update["queue_size"] == 5  # 3 + 2
        assert update["direction"] == "forward"
        assert update["last_node"] == "Page A"
        assert update["current_depth"] == 0

    def test_backward_direction_tracked_separately(self):
        received = []
        queue_svc = Mock()
        queue_svc.length.return_value = 0

        agg = BidirProgressAggregator(received.append, queue_svc, "fwd_q", "bwd_q")
        agg.record("End", 0, "backward")

        assert received[0]["direction"] == "backward"
        assert agg._bwd_nodes == 1
        assert agg._fwd_nodes == 0

    def test_callback_called_once_per_record(self):
        callback = Mock()
        agg = self._make_agg(callback)

        for i in range(5):
            agg.record(f"Page {i}", i, "forward")

        assert callback.call_count == 5
        assert agg.total_nodes == 5


class TestBidirectionalBFSPathFinder:
    """Integration tests for bidirectional BFS pathfinding."""

    def test_bidirectional_direct_connection(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Test that bidirectional BFS finds a direct connection."""
        mock_wikipedia_client.page_exists.return_value = True
        # Forward: Page A links to Page B
        mock_wikipedia_client.get_links_bulk.return_value = {"Page A": ["Page B"]}
        # Backward: nothing needed if forward finds it immediately
        mock_wikipedia_client.get_backlinks_bulk.return_value = {"Page B": []}

        pathfinder = BidirectionalBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service, max_depth=6
        )

        result = pathfinder.find_path("Page A", "Page B")

        assert "Page A" in result["path"]
        assert "Page B" in result["path"]
        assert "nodes_explored" in result

    def test_bidirectional_same_page(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Test bidirectional BFS when start and end are the same."""
        pathfinder = BidirectionalBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        result = pathfinder.find_path("Page A", "Page A")
        assert result["path"] == ["Page A"]
        assert result["nodes_explored"] == 1

    def test_bidirectional_invalid_empty_pages(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Empty page names raise InvalidPageError."""
        pathfinder = BidirectionalBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        with pytest.raises(InvalidPageError):
            pathfinder.find_path("", "Page B")

        with pytest.raises(InvalidPageError):
            pathfinder.find_path("Page A", "")

    def test_bidirectional_no_path_found(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """PathNotFoundError is raised when frontiers cannot meet."""

        def isolated_links(pages, on_page_fetched=None):
            return {page: [] for page in pages}

        mock_wikipedia_client.get_links_bulk.side_effect = isolated_links
        mock_wikipedia_client.get_backlinks_bulk.side_effect = isolated_links

        pathfinder = BidirectionalBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service, max_depth=2
        )

        with pytest.raises(PathNotFoundError):
            pathfinder.find_path("Page A", "Page B")

    def test_bidirectional_progress_callback(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Progress callback fires when provided to BidirectionalBFSPathFinder."""
        progress_calls = []

        def fwd_links(pages, on_page_fetched=None):
            mapping = {"Page A": ["Page B"]}
            if on_page_fetched:
                for p in pages:
                    on_page_fetched(p, mapping.get(p, []))
            return {p: mapping.get(p, []) for p in pages}

        mock_wikipedia_client.get_links_bulk.side_effect = fwd_links
        mock_wikipedia_client.get_backlinks_bulk.return_value = {}

        pathfinder = BidirectionalBFSPathFinder(
            mock_wikipedia_client,
            mock_cache_service,
            mock_queue_service,
            progress_callback=lambda d: progress_calls.append(d),
        )

        pathfinder.find_path("Page A", "Page B")
        assert len(progress_calls) > 0


class TestPathfindingErrorHandling:
    """Integration tests for pathfinding error scenarios."""

    def test_wikipedia_api_error_handling(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """WikipediaAPIError from get_links_bulk propagates out of find_path."""
        from app.utils.exceptions import WikipediaAPIError

        mock_wikipedia_client.page_exists.return_value = True
        mock_wikipedia_client.get_links_bulk.side_effect = WikipediaAPIError(
            "API request failed"
        )

        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        with pytest.raises(WikipediaAPIError):
            pathfinder.find_path("Page A", "Page B")

    def test_cache_error_handling(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """CacheConnectionError from set_add propagates out of find_path."""
        from app.utils.exceptions import CacheConnectionError

        mock_wikipedia_client.page_exists.return_value = True
        mock_cache_service.set_add.side_effect = CacheConnectionError(
            "Redis connection failed"
        )

        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        with pytest.raises(CacheConnectionError):
            pathfinder.find_path("Page A", "Page B")

    def test_queue_error_handling(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """CacheConnectionError from queue.push propagates out of find_path."""
        from app.utils.exceptions import CacheConnectionError

        mock_wikipedia_client.page_exists.return_value = True
        mock_queue_service.push.side_effect = CacheConnectionError(
            "Queue operation failed"
        )

        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        with pytest.raises(CacheConnectionError):
            pathfinder.find_path("Page A", "Page B")
