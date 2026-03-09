import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

from app.core.interfaces import (
    CacheServiceInterface,
    PathFinderInterface,
    QueueInterface,
    WikipediaClientInterface,
)
from app.utils.exceptions import (
    CacheConnectionError,
    InvalidPageError,
    PathNotFoundError,
    WikipediaAPIError,
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
        progress_callback: Callable | None = None,
    ):
        self.wikipedia_client = wikipedia_client
        self.cache_service = cache_service
        self.queue_service = queue_service
        self.max_depth = max_depth
        self.batch_size = batch_size
        self.progress_callback = progress_callback

    def find_path(self, start_page: str, end_page: str) -> dict[str, Any]:
        """
        Find a path using Redis-based BFS to minimize memory usage.

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
    ) -> dict[str, Any]:
        """Perform the actual BFS search using Redis for state management.

        Nodes are popped from the queue in batches and their links are fetched
        in a single bulk Wikipedia API call per batch, minimising round-trips.
        """
        logger.info(
            f"Starting Redis-based BFS from '{start_page}' to '{end_page}' (session: {session_id})"
        )

        # Initialize search state
        self.queue_service.push(queue_key, {"page": start_page, "depth": 0})
        self.cache_service.set(f"{visited_key}:{start_page}", True, ttl=3600)
        self.cache_service.set(f"{paths_key}:{start_page}", [start_page], ttl=3600)

        nodes_explored = 0
        nodes_lock = threading.Lock()
        search_start_time = time.time()

        while self.queue_service.length(queue_key) > 0:
            # Pop a batch of nodes and fetch their links in one API call
            batch_items = self.queue_service.pop_batch(queue_key, self.batch_size)
            if not batch_items:
                break

            current_depth = batch_items[0]["depth"]

            # BFS guarantees monotonically increasing depth — check on first item
            if current_depth > self.max_depth:
                logger.warning(
                    f"Reached maximum depth {self.max_depth}, stopping search"
                )
                break

            # Build a per-page callback fired inside the thread pool as each
            # Wikipedia response arrives.  This spreads progress updates across
            # the network round-trip window, giving the client smooth real-time
            # feedback instead of a single jump after the full batch completes.
            # nodes_lock guards nodes_explored against concurrent increments.
            #
            # _depth captures current_depth by value (avoids ruff B023: loop
            # variable capture).  if/else lets basedpyright infer the correct
            # Callable | None union without a redundant pre-declaration.
            # Pre-declare so basedpyright knows the union type across both branches.
            on_page_fetched: Callable[[str, list[str]], None] | None = None
            if self.progress_callback:

                def _on_page_fetched(
                    title: str,
                    _links: list[str],
                    *,
                    _d: int = current_depth,  # default arg binds value at def time (B023)
                ) -> None:
                    nonlocal nodes_explored
                    with nodes_lock:
                        nodes_explored += 1
                        count = nodes_explored
                    self.progress_callback(  # type: ignore[misc]
                        {
                            "status": "Searching...",
                            "search_stats": {
                                "nodes_explored": count,
                                "current_depth": _d,
                                "last_node": title,
                                "queue_size": self.queue_service.length(queue_key),
                            },
                            "search_time_elapsed": round(
                                time.time() - search_start_time, 2
                            ),
                        }
                    )

                on_page_fetched = _on_page_fetched

            # Bulk-fetch links for all pages in the batch (parallel API calls)
            page_names = [item["page"] for item in batch_items]
            logger.info(
                f"Fetching links for batch of {len(page_names)} pages at depth {current_depth}"
            )
            try:
                links_bulk = self.wikipedia_client.get_links_bulk(
                    page_names, on_page_fetched
                )
                # When no progress callback is set, on_page_fetched is None and
                # nodes_explored is never incremented inside the callback — do it here.
                if on_page_fetched is None:
                    nodes_explored += len(batch_items)
            except Exception as e:
                logger.error(
                    f"Failed to get links for batch at depth {current_depth}: {e}"
                )
                if isinstance(e, WikipediaAPIError | CacheConnectionError):
                    raise
                continue

            # Process each page in the batch
            for item in batch_items:
                current_page = item["page"]
                links = links_bulk.get(current_page, [])
                logger.info(f"Found {len(links)} links from '{current_page}'")

                current_path = self.cache_service.get(f"{paths_key}:{current_page}")
                if not current_path:
                    logger.warning(f"No path found for {current_page}, skipping")
                    continue

                for link in links:
                    if link == end_page:
                        final_path = current_path + [link]
                        logger.info(
                            f"Path found! Length: {len(final_path)}, explored {nodes_explored} nodes"
                        )
                        return {"path": final_path, "nodes_explored": nodes_explored}

                    visited_check_key = f"{visited_key}:{link}"
                    try:
                        if self.cache_service.exists(visited_check_key):
                            continue
                        self.cache_service.set(visited_check_key, True, ttl=3600)
                        new_path = current_path + [link]
                        self.cache_service.set(
                            f"{paths_key}:{link}", new_path, ttl=3600
                        )
                        self.queue_service.push(
                            queue_key, {"page": link, "depth": item["depth"] + 1}
                        )
                    except Exception as e:
                        logger.error(f"Cache operation failed for {link}: {e}")
                        if isinstance(e, CacheConnectionError):
                            raise
                        continue

                # Fire once per page after its links are enqueued so queue_size
                # reflects the newly added nodes.  This covers the link-processing
                # gap where no Wikipedia fetch is in flight and the UI would
                # otherwise stall between batches.
                if self.progress_callback:
                    self.progress_callback(
                        {
                            "status": "Searching...",
                            "search_stats": {
                                "nodes_explored": nodes_explored,
                                "current_depth": current_depth,
                                "last_node": current_page,
                                "queue_size": self.queue_service.length(queue_key),
                            },
                            "search_time_elapsed": round(
                                time.time() - search_start_time, 2
                            ),
                        }
                    )

            logger.info(
                f"Processed batch of {len(batch_items)} pages, queue length: {self.queue_service.length(queue_key)}"
            )

        logger.warning(f"No path found from '{start_page}' to '{end_page}'")
        raise PathNotFoundError(start_page, end_page)

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

    def find_path(self, start_page: str, end_page: str) -> dict[str, Any]:
        """
        Find a path using bidirectional BFS.

        This implementation is more complex but can be significantly faster
        for longer paths as it reduces the search space exponentially.
        """
        # Implementation would be similar to above but maintain two search frontiers
        # For now, fall back to regular BFS
        regular_finder = RedisBasedBFSPathFinder(
            self.wikipedia_client, self.cache_service, self.queue_service
        )
        return regular_finder.find_path(start_page, end_page)
