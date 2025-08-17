import uuid
from typing import List, Set, Dict, Optional, Any
from app.core.interfaces import (
    PathFinderInterface,
    WikipediaClientInterface,
    CacheServiceInterface,
    QueueInterface,
)
from app.utils.exceptions import (
    PathNotFoundError,
    InvalidPageError,
    WikipediaPageNotFoundError,
)
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RedisBasedBFSPathFinder(PathFinderInterface):
    """
    Redis-based BFS pathfinding algorithm that avoids holding large queues in memory.
    Uses Redis queues for BFS state management and Redis sets for visited tracking.
    """

    def __init__(
        self,
        wikipedia_client: WikipediaClientInterface,
        cache_service: CacheServiceInterface,
        queue_service: QueueInterface,
        max_depth: int = 6,
        batch_size: int = 50,
        progress_callback: Optional[callable] = None,
    ):
        self.wikipedia_client = wikipedia_client
        self.cache_service = cache_service
        self.queue_service = queue_service
        self.max_depth = max_depth
        self.batch_size = batch_size
        self.progress_callback = progress_callback

    def find_shortest_path(self, start_page: str, end_page: str) -> Dict[str, Any]:
        """
        Find shortest path using Redis-based BFS to minimize memory usage.

        Args:
            start_page: Starting Wikipedia page
            end_page: Target Wikipedia page

        Returns:
            Dict with 'path' (List[str]) and 'nodes_explored' (int)

        Raises:
            PathNotFoundError: When no path exists
            InvalidPageError: When start or end page doesn't exist
        """
        # Validate input pages
        if not start_page or not end_page:
            raise InvalidPageError("Start and end pages cannot be empty")

        if start_page == end_page:
            return {"path": [start_page], "nodes_explored": 1}

        # Check if pages exist
        if not self.wikipedia_client.page_exists(start_page):
            raise InvalidPageError(f"Start page '{start_page}' does not exist")

        if not self.wikipedia_client.page_exists(end_page):
            raise InvalidPageError(f"End page '{end_page}' does not exist")

        # Generate unique session ID for this search
        session_id = str(uuid.uuid4())
        queue_key = f"bfs_queue:{session_id}"
        visited_key = f"bfs_visited:{session_id}"
        paths_key = f"bfs_paths:{session_id}"

        try:
            return self._perform_bfs_search(
                start_page, end_page, session_id, queue_key, visited_key, paths_key
            )
        finally:
            # Clean up Redis keys
            self._cleanup_search_state(queue_key, visited_key, paths_key)

    def _perform_bfs_search(
        self,
        start_page: str,
        end_page: str,
        session_id: str,
        queue_key: str,
        visited_key: str,
        paths_key: str,
    ) -> Dict[str, Any]:
        """Perform the actual BFS search using Redis for state management."""

        logger.info(
            f"Starting Redis-based BFS from '{start_page}' to '{end_page}' (session: {session_id})"
        )

        # Initialize search state
        self.queue_service.push(queue_key, {"page": start_page, "depth": 0})
        self.cache_service.set(
            f"{visited_key}:{start_page}", True, ttl=3600
        )  # 1 hour TTL
        self.cache_service.set(
            f"{paths_key}:{start_page}", [start_page], ttl=3600
        )  # 1 hour TTL

        # Simple BFS: process one item at a time from the queue
        nodes_explored = 0
        import time
        search_start_time = time.time()

        while self.queue_service.length(queue_key) > 0:
            current_item = self.queue_service.pop(queue_key)
            if not current_item:
                break

            current_page = current_item["page"]
            current_depth = current_item["depth"]
            nodes_explored += 1

            logger.info(
                f"Processing page '{current_page}' at depth {current_depth} (node #{nodes_explored})"
            )

            # Report progress every 3 nodes
            if (self.progress_callback and nodes_explored % 3 == 0):
                queue_size = self.queue_service.length(queue_key)
                elapsed_time = time.time() - search_start_time
                
                self.progress_callback({
                    "status": "Searching...",
                    "search_stats": {
                        "nodes_explored": nodes_explored,
                        "current_depth": current_depth,
                        "last_node": current_page,
                        "queue_size": queue_size,
                    },
                    "search_time_elapsed": round(elapsed_time, 2)
                })

            # Check depth limit
            if current_depth > self.max_depth:
                logger.warning(
                    f"Reached maximum depth {self.max_depth}, stopping search"
                )
                break

            # Get the current path for this page
            current_path_key = f"{paths_key}:{current_page}"
            current_path = self.cache_service.get(current_path_key)

            if not current_path:
                logger.warning(f"No path found for {current_page}, skipping")
                continue

            # Get links for this page
            try:
                links_bulk = self.wikipedia_client.get_links_bulk([current_page])
                links = links_bulk.get(current_page, [])
                logger.info(f"Found {len(links)} links from '{current_page}'")
            except Exception as e:
                logger.error(f"Failed to get links for {current_page}: {e}")
                # Re-raise WikipediaAPIError and other critical errors
                from app.utils.exceptions import WikipediaAPIError, CacheConnectionError

                if isinstance(e, (WikipediaAPIError, CacheConnectionError)):
                    raise
                continue

            # Process each link
            for link in links:
                # Check if we found the target
                if link == end_page:
                    final_path = current_path + [link]
                    logger.info(
                        f"Path found! Length: {len(final_path)}, explored {nodes_explored} nodes"
                    )
                    return {"path": final_path, "nodes_explored": nodes_explored}

                # Check if already visited
                visited_check_key = f"{visited_key}:{link}"
                try:
                    if self.cache_service.exists(visited_check_key):
                        continue

                    # Mark as visited and store path (with TTL to prevent accumulation)
                    self.cache_service.set(
                        visited_check_key, True, ttl=3600
                    )  # 1 hour TTL
                    new_path = current_path + [link]
                    self.cache_service.set(
                        f"{paths_key}:{link}", new_path, ttl=3600
                    )  # 1 hour TTL

                    # Add to queue for next level
                    self.queue_service.push(
                        queue_key, {"page": link, "depth": current_depth + 1}
                    )
                except Exception as e:
                    logger.error(f"Cache operation failed for {link}: {e}")
                    # Re-raise CacheConnectionError and other critical cache errors
                    from app.utils.exceptions import CacheConnectionError

                    if isinstance(e, CacheConnectionError):
                        raise
                    continue

            logger.info(
                f"Finished processing '{current_page}', queue length: {self.queue_service.length(queue_key)}"
            )

        logger.warning(f"No path found from '{start_page}' to '{end_page}'")
        raise PathNotFoundError(start_page, end_page)

    def _process_depth_level(
        self,
        pages_at_depth: List[str],
        end_page: str,
        queue_key: str,
        visited_key: str,
        paths_key: str,
        depth: int,
    ) -> Optional[List[str]]:
        """Process all pages at a specific depth level."""

        logger.info(f"Processing depth {depth} with {len(pages_at_depth)} pages")

        # Get links for all pages in this batch
        try:
            bulk_links = self.wikipedia_client.get_links_bulk(pages_at_depth)
        except Exception as e:
            logger.error(f"Failed to get links for batch at depth {depth}: {e}")
            return None

        # Process each page's links
        next_level_pages = []

        for current_page in pages_at_depth:
            links = bulk_links.get(current_page, [])
            current_path_key = f"{paths_key}:{current_page}"
            current_path = self.cache_service.get(current_path_key)

            if not current_path:
                logger.warning(f"No path found for {current_page}, skipping")
                continue

            for link in links:
                # Check if we found the target
                if link == end_page:
                    final_path = current_path + [link]
                    logger.info(f"Path found! Length: {len(final_path)}")
                    return final_path

                # Check if already visited
                visited_check_key = f"{visited_key}:{link}"
                if self.cache_service.exists(visited_check_key):
                    continue

                # Mark as visited and store path (with TTL to prevent accumulation)
                self.cache_service.set(visited_check_key, True, ttl=3600)  # 1 hour TTL
                new_path = current_path + [link]
                self.cache_service.set(
                    f"{paths_key}:{link}", new_path, ttl=3600
                )  # 1 hour TTL

                next_level_pages.append({"page": link, "depth": depth + 1})

        # Add next level pages to queue
        if next_level_pages:
            self.queue_service.push_batch(queue_key, next_level_pages)
            logger.info(
                f"Added {len(next_level_pages)} pages to next level (depth {depth + 1})"
            )

        return None

    def _cleanup_search_state(
        self, queue_key: str, visited_key: str, paths_key: str
    ) -> None:
        """Clean up Redis keys used during search."""
        try:
            # Clear the queue completely
            self.queue_service.clear(queue_key)
            logger.debug(f"Cleared queue: {queue_key}")

            # Clean up visited and paths keys using pattern matching
            visited_pattern = f"{visited_key}:*"
            paths_pattern = f"{paths_key}:*"

            visited_cleared = self.cache_service.clear_pattern(visited_pattern)
            paths_cleared = self.cache_service.clear_pattern(paths_pattern)

            logger.info(
                f"Search state cleanup completed - cleared {visited_cleared} visited keys, {paths_cleared} path keys"
            )
        except Exception as e:
            logger.error(f"Failed to cleanup search state: {e}")


class BidirectionalBFSPathFinder(PathFinderInterface):
    """
    Bidirectional BFS implementation that searches from both start and end pages.
    More efficient for finding paths in large graphs.
    """

    def __init__(
        self,
        wikipedia_client: WikipediaClientInterface,
        cache_service: CacheServiceInterface,
        queue_service: QueueInterface,
        max_depth: int = 3,  # Lower max depth since we search from both ends
    ):
        self.wikipedia_client = wikipedia_client
        self.cache_service = cache_service
        self.queue_service = queue_service
        self.max_depth = max_depth

    def find_shortest_path(self, start_page: str, end_page: str) -> Dict[str, Any]:
        """
        Find shortest path using bidirectional BFS.

        This implementation is more complex but can be significantly faster
        for longer paths as it reduces the search space exponentially.
        """
        # Implementation would be similar to above but maintain two search frontiers
        # For now, fall back to regular BFS
        regular_finder = RedisBasedBFSPathFinder(
            self.wikipedia_client, self.cache_service, self.queue_service
        )
        return regular_finder.find_shortest_path(start_page, end_page)
