from unittest.mock import Mock

import pytest

from app.core.pathfinding import BidirectionalBFSPathFinder, RedisBasedBFSPathFinder
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

    def test_find_path_nonexistent_start_page(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Test pathfinding when start page doesn't exist."""
        # Mock start page doesn't exist
        mock_wikipedia_client.page_exists.side_effect = lambda page: (
            page != "NonExistent"
        )

        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        with pytest.raises(
            InvalidPageError, match="Start page 'NonExistent' does not exist"
        ):
            pathfinder.find_path("NonExistent", "Page B")

    def test_find_path_nonexistent_end_page(
        self, mock_wikipedia_client, mock_cache_service, mock_queue_service
    ):
        """Test pathfinding when end page doesn't exist."""
        # Mock end page doesn't exist
        mock_wikipedia_client.page_exists.side_effect = lambda page: (
            page != "NonExistent"
        )

        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        with pytest.raises(
            InvalidPageError, match="End page 'NonExistent' does not exist"
        ):
            pathfinder.find_path("Page A", "NonExistent")

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

        def mock_pop_batch(queue_name, count):
            if queue_name not in queue_data:
                return []
            batch = queue_data[queue_name][:count]
            queue_data[queue_name] = queue_data[queue_name][count:]
            return batch

        mock_queue_service = Mock()
        mock_queue_service.push.side_effect = mock_push
        mock_queue_service.pop.side_effect = mock_pop
        mock_queue_service.length.side_effect = mock_length
        mock_queue_service.clear.side_effect = mock_clear
        mock_queue_service.push_batch.side_effect = mock_push_batch
        mock_queue_service.pop_batch.side_effect = mock_pop_batch

        # Mock simple path A -> B
        mock_wikipedia_client.page_exists.return_value = True
        mock_wikipedia_client.get_links_bulk.return_value = {"Page A": ["Page B"]}

        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        result = pathfinder.find_path("Page A", "Page B")

        assert result["path"] == ["Page A", "Page B"]
        assert "nodes_explored" in result
        # Verify queue operations were called
        assert mock_queue_service.push.called
        assert mock_queue_service.pop_batch.called

    def test_redis_ops_integration(self, mock_wikipedia_client, mock_queue_service):
        """Test that Redis SET/Hash operations work correctly for visited tracking."""
        # Use the shared mock_cache_service fixture approach but inline here
        visited_sets: dict = {}
        parent_hashes: dict = {}

        mock_redis = Mock()

        def _sadd(key, *members):
            if key not in visited_sets:
                visited_sets[key] = set()
            visited_sets[key].update(members)
            return 1

        def _sismember(key, member):
            return member in visited_sets.get(key, set())

        def _hset(key, field, value):
            if key not in parent_hashes:
                parent_hashes[key] = {}
            parent_hashes[key][field] = value
            return 1

        def _hget(key, field):
            return parent_hashes.get(key, {}).get(field)

        def _delete(*keys):
            for key in keys:
                visited_sets.pop(key, None)
                parent_hashes.pop(key, None)
            return len(keys)

        mock_redis.sadd.side_effect = _sadd
        mock_redis.sismember.side_effect = _sismember
        mock_redis.hset.side_effect = _hset
        mock_redis.hget.side_effect = _hget
        mock_redis.delete.side_effect = _delete

        class MockPipeline:
            def __init__(self):
                self._cmds = []

            def sadd(self, key, *members):
                self._cmds.append(("sadd", key, members))
                return self

            def sismember(self, key, member):
                self._cmds.append(("sismember", key, member))
                return self

            def hset(self, key, field, value):
                self._cmds.append(("hset", key, field, value))
                return self

            def delete(self, *keys):
                self._cmds.append(("delete", keys))
                return self

            def execute(self):
                results = []
                for cmd in self._cmds:
                    if cmd[0] == "sadd":
                        results.append(_sadd(cmd[1], *cmd[2]))
                    elif cmd[0] == "sismember":
                        results.append(_sismember(cmd[1], cmd[2]))
                    elif cmd[0] == "hset":
                        results.append(_hset(cmd[1], cmd[2], cmd[3]))
                    elif cmd[0] == "delete":
                        results.append(_delete(*cmd[1]))
                    else:
                        results.append(None)
                self._cmds = []
                return results

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        mock_redis.pipeline.side_effect = lambda: MockPipeline()

        mock_cache_service = Mock()
        mock_cache_service.redis_client = mock_redis

        # Mock simple path A -> B
        mock_wikipedia_client.page_exists.return_value = True
        mock_wikipedia_client.get_links_bulk.return_value = {"Page A": ["Page B"]}

        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        result = pathfinder.find_path("Page A", "Page B")

        assert result["path"] == ["Page A", "Page B"]
        assert "nodes_explored" in result
        # Verify Redis SET operations were called for visited tracking
        assert mock_redis.sadd.called
        assert mock_redis.hset.called


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
            pathfinder.find_path("Page A", "Page B")

    def test_cache_error_handling(self, mock_wikipedia_client, mock_queue_service):
        """Test handling of Redis errors during BFS state operations."""
        from app.utils.exceptions import CacheConnectionError

        # Mock cache service with a redis_client that raises on sadd
        mock_cache_service = Mock()
        mock_redis = Mock()
        mock_redis.sadd.side_effect = CacheConnectionError("Redis connection failed")
        mock_cache_service.redis_client = mock_redis

        mock_wikipedia_client.page_exists.return_value = True
        # Set up links that don't immediately lead to target, forcing sadd call
        mock_wikipedia_client.get_links_bulk.return_value = {
            "Page A": ["Page C", "Page D"]
        }

        pathfinder = RedisBasedBFSPathFinder(
            mock_wikipedia_client, mock_cache_service, mock_queue_service
        )

        with pytest.raises(CacheConnectionError):
            pathfinder.find_path("Page A", "Page B")

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
            pathfinder.find_path("Page A", "Page B")
