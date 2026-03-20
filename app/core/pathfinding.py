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
from app.utils.constants import (
    BFS_BWD_PARENT_PREFIX,
    BFS_BWD_QUEUE_PREFIX,
    BFS_BWD_VISITED_PREFIX,
    BFS_FWD_PARENT_PREFIX,
    BFS_FWD_QUEUE_PREFIX,
    BFS_FWD_VISITED_PREFIX,
    BFS_PARENT_PREFIX,
    BFS_QUEUE_PREFIX,
    BFS_VISITED_PREFIX,
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
    Uses Redis queues for BFS state management and Redis sets/hashes for visited tracking.
    """

    def __init__(
        self,
        wikipedia_client: WikipediaClientInterface,
        cache_service: CacheServiceInterface,
        queue_service: QueueInterface,
        max_depth: int = 6,
        batch_size: int = 20,
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

        # Generate unique session ID for this search
        session_id = str(uuid.uuid4())
        queue_key = f"{BFS_QUEUE_PREFIX}:{session_id}"
        visited_key = f"{BFS_VISITED_PREFIX}:{session_id}"
        parent_key = f"{BFS_PARENT_PREFIX}:{session_id}"

        try:
            return self._perform_bfs_search(
                start_page, end_page, session_id, queue_key, visited_key, parent_key
            )
        finally:
            # Clean up Redis keys
            self._cleanup_search_state(queue_key, visited_key, parent_key)

    def _perform_bfs_search(
        self,
        start_page: str,
        end_page: str,
        session_id: str,
        queue_key: str,
        visited_key: str,
        parent_key: str,
    ) -> dict[str, Any]:
        """Perform the actual BFS search using Redis for state management.

        Nodes are popped from the queue in batches and their links are fetched
        in a single bulk Wikipedia API call per batch, minimising round-trips.
        """
        logger.info(
            "bfs_started",
            extra={"start_page": start_page, "end_page": end_page, "session_id": session_id},
        )

        # Initialize search state
        self.queue_service.push(queue_key, {"page": start_page, "depth": 0})
        self.cache_service.set_add(visited_key, start_page)

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
                logger.warning("max_depth_reached", extra={"max_depth": self.max_depth})
                break

            # Build a per-page callback fired inside the thread pool as each
            # Wikipedia response arrives.  This spreads progress updates across
            # the network round-trip window, giving the client smooth real-time
            # feedback instead of a single jump after the full batch completes.
            # nodes_lock guards nodes_explored against concurrent increments.
            #
            # _depth captures current_depth by value (avoids ruff B023: loop
            # variable capture).  Pre-declare so basedpyright knows the union
            # type across both branches of the if/else below.
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
                "fetching_batch",
                extra={"batch_size": len(page_names), "depth": current_depth},
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
                logger.error("batch_links_failed", extra={"depth": current_depth, "error": str(e)})
                if isinstance(e, WikipediaAPIError | CacheConnectionError):
                    raise
                continue

            # Process each page in the batch
            for item in batch_items:
                current_page = item["page"]
                links = links_bulk.get(current_page, [])
                logger.info("page_links_fetched", extra={"page": current_page, "link_count": len(links)})

                for link in links:
                    if link == end_page:
                        self.cache_service.hash_set(parent_key, link, current_page)
                        final_path = self._reconstruct_path(end_page, parent_key)
                        logger.info(
                            "path_found",
                            extra={"path_length": len(final_path), "nodes_explored": nodes_explored},
                        )
                        return {"path": final_path, "nodes_explored": nodes_explored}

                    try:
                        if self.cache_service.set_contains(visited_key, link):
                            continue
                        self.cache_service.set_add(visited_key, link)
                        self.cache_service.hash_set(parent_key, link, current_page)
                        self.queue_service.push(
                            queue_key, {"page": link, "depth": item["depth"] + 1}
                        )
                    except Exception as e:
                        logger.error("redis_op_failed", extra={"link": link, "error": str(e)})
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
                "batch_processed",
                extra={"batch_size": len(batch_items), "queue_length": self.queue_service.length(queue_key)},
            )

        logger.warning("path_not_found", extra={"start_page": start_page, "end_page": end_page})
        raise PathNotFoundError(start_page, end_page)

    def _reconstruct_path(self, node: str, parent_hash_key: str) -> list[str]:
        """Reconstruct the path from start to node via the parent hash."""
        path = [node]
        while True:
            parent = self.cache_service.hash_get(parent_hash_key, path[-1])
            if parent is None:
                break
            path.append(parent)
        path.reverse()
        return path

    def _cleanup_search_state(
        self, queue_key: str, visited_key: str, parent_key: str
    ) -> None:
        """Clean up Redis keys used during search."""
        try:
            self.cache_service.delete_many([queue_key, visited_key, parent_key])
            logger.info("Search state cleanup completed")
        except Exception as e:
            logger.error("search_cleanup_failed", extra={"error": str(e)})


class BidirProgressAggregator:
    """
    Combines progress from two concurrent BFS frontiers before firing the
    real progress callback.  Each frontier calls ``record(title, depth,
    direction)`` from its ``on_page_fetched`` thread; the aggregator owns
    all shared counters under a single lock so neither frontier needs to
    know about the other.
    """

    def __init__(
        self,
        callback: Callable,
        queue_service: QueueInterface,
        fwd_q: str,
        bwd_q: str,
    ) -> None:
        self._callback = callback
        self._queue_service = queue_service
        self._fwd_q = fwd_q
        self._bwd_q = bwd_q
        self._fwd_nodes = 0
        self._bwd_nodes = 0
        self._fwd_depth = 0
        self._bwd_depth = 0
        self._start_time = time.time()
        self._lock = threading.Lock()

    def record(self, title: str, depth: int, direction: str) -> None:
        with self._lock:
            if direction == "forward":
                self._fwd_nodes += 1
                self._fwd_depth = max(self._fwd_depth, depth)
            else:
                self._bwd_nodes += 1
                self._bwd_depth = max(self._bwd_depth, depth)
            combined_queue = self._queue_service.length(
                self._fwd_q
            ) + self._queue_service.length(self._bwd_q)
            self._callback(
                {
                    "nodes_explored": self._fwd_nodes + self._bwd_nodes,
                    "queue_size": combined_queue,
                    "current_depth": self._fwd_depth + self._bwd_depth,
                    "last_node": title,
                    "direction": direction,
                    "search_time_elapsed": round(time.time() - self._start_time, 2),
                }
            )

    @property
    def total_nodes(self) -> int:
        return self._fwd_nodes + self._bwd_nodes


class BidirectionalBFSPathFinder(PathFinderInterface):
    """
    Bidirectional BFS implementation that searches from both start and end pages.
    The forward frontier follows outgoing links; the backward frontier follows
    backlinks (pages that link *to* the current node).  When the two frontiers
    meet, the full path is reconstructed.
    """

    def __init__(
        self,
        wikipedia_client: WikipediaClientInterface,
        cache_service: CacheServiceInterface,
        queue_service: QueueInterface,
        max_depth: int = 6,
        batch_size: int = 20,
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
        Find a path using bidirectional BFS.

        Returns:
            Dict with 'path' (List[str]) and 'nodes_explored' (int)

        Raises:
            PathNotFoundError: When no path exists within max_depth
            InvalidPageError: When start or end page doesn't exist
        """
        if not start_page or not end_page:
            raise InvalidPageError("Start and end pages cannot be empty")

        if start_page == end_page:
            return {"path": [start_page], "nodes_explored": 1}

        sid = str(uuid.uuid4())[:8]

        fwd_q = f"{BFS_FWD_QUEUE_PREFIX}:{sid}"
        bwd_q = f"{BFS_BWD_QUEUE_PREFIX}:{sid}"
        fwd_vis = f"{BFS_FWD_VISITED_PREFIX}:{sid}"
        bwd_vis = f"{BFS_BWD_VISITED_PREFIX}:{sid}"
        fwd_par = f"{BFS_FWD_PARENT_PREFIX}:{sid}"
        bwd_par = f"{BFS_BWD_PARENT_PREFIX}:{sid}"

        keys = [fwd_q, bwd_q, fwd_vis, bwd_vis, fwd_par, bwd_par]

        tracker = (
            BidirProgressAggregator(
                self.progress_callback, self.queue_service, fwd_q, bwd_q
            )
            if self.progress_callback
            else None
        )

        try:
            self.cache_service.set_add(fwd_vis, start_page)
            self.cache_service.set_add(bwd_vis, end_page)
            self.queue_service.push(fwd_q, {"page": start_page, "depth": 0})
            self.queue_service.push(bwd_q, {"page": end_page, "depth": 0})

            fwd_max = (self.max_depth + 1) // 2
            bwd_max = self.max_depth // 2

            path = self._run_bidir_bfs(
                start_page,
                end_page,
                fwd_q,
                bwd_q,
                fwd_vis,
                bwd_vis,
                fwd_par,
                bwd_par,
                fwd_max,
                bwd_max,
                tracker,
            )
            return {
                "path": path,
                "nodes_explored": tracker.total_nodes if tracker else 0,
            }
        finally:
            self.cache_service.delete_many(keys)

    def _run_bidir_bfs(
        self,
        start_page: str,
        end_page: str,
        fwd_q: str,
        bwd_q: str,
        fwd_vis: str,
        bwd_vis: str,
        fwd_par: str,
        bwd_par: str,
        fwd_max: int,
        bwd_max: int,
        tracker: BidirProgressAggregator | None,
    ) -> list[str]:
        while True:
            fwd_size = self.queue_service.length(fwd_q)
            bwd_size = self.queue_service.length(bwd_q)

            if fwd_size == 0 and bwd_size == 0:
                break

            if bwd_size > 0 and (fwd_size == 0 or bwd_size < fwd_size):
                meeting = self._expand_backward_batch(
                    end_page,
                    bwd_q,
                    bwd_vis,
                    bwd_par,
                    fwd_vis,
                    fwd_par,
                    bwd_max,
                    tracker,
                )
            else:
                meeting = self._expand_forward_batch(
                    start_page,
                    fwd_q,
                    fwd_vis,
                    fwd_par,
                    bwd_vis,
                    bwd_par,
                    fwd_max,
                    tracker,
                )

            if meeting is not None:
                return self._reconstruct_bidir_path(
                    meeting, start_page, end_page, fwd_par, bwd_par
                )

        raise PathNotFoundError(start_page, end_page)

    def _expand_forward_batch(
        self,
        start_page: str,
        fwd_q: str,
        fwd_vis: str,
        fwd_par: str,
        bwd_vis: str,
        bwd_par: str,
        fwd_max: int,
        tracker: BidirProgressAggregator | None,
    ) -> str | None:
        batch = self.queue_service.pop_batch(fwd_q, self.batch_size)
        if not batch:
            return None

        depth = batch[0]["depth"]
        if depth >= fwd_max:
            return None

        page_names = [item["page"] for item in batch]

        def on_page_fetched(_title: str, _links: list[str], *, _d: int = depth) -> None:
            if tracker:
                tracker.record(_title, _d, "forward")

        links_bulk = self.wikipedia_client.get_links_bulk(page_names, on_page_fetched)
        meeting_candidates: list[str] = []

        for item in batch:
            page = item["page"]
            links = links_bulk.get(page, [])

            if not links:
                continue

            already_visited = self.cache_service.set_contains_many(fwd_vis, links)
            new_links = [
                lnk
                for lnk, seen in zip(links, already_visited, strict=False)
                if not seen
            ]

            if not new_links:
                continue

            in_bwd = self.cache_service.set_contains_many(bwd_vis, new_links)
            self.cache_service.set_add_many(fwd_vis, new_links)
            self.cache_service.hash_set_many(fwd_par, {lnk: page for lnk in new_links})

            self.queue_service.push_batch(
                fwd_q, [{"page": lnk, "depth": depth + 1} for lnk in new_links]
            )

            for link, is_meeting in zip(new_links, in_bwd, strict=False):
                if is_meeting:
                    meeting_candidates.append(link)

        if meeting_candidates:
            return self._pick_shortest(meeting_candidates, fwd_par, bwd_par)
        return None

    def _expand_backward_batch(
        self,
        end_page: str,
        bwd_q: str,
        bwd_vis: str,
        bwd_par: str,
        fwd_vis: str,
        fwd_par: str,
        bwd_max: int,
        tracker: BidirProgressAggregator | None,
    ) -> str | None:
        batch = self.queue_service.pop_batch(bwd_q, self.batch_size)
        if not batch:
            return None

        depth = batch[0]["depth"]
        if depth >= bwd_max:
            return None

        page_names = [item["page"] for item in batch]

        def on_page_fetched(_title: str, _links: list[str], *, _d: int = depth) -> None:
            if tracker:
                tracker.record(_title, _d, "backward")

        links_bulk = self.wikipedia_client.get_backlinks_bulk(
            page_names, on_page_fetched
        )
        meeting_candidates: list[str] = []

        for item in batch:
            page = item["page"]
            links = links_bulk.get(page, [])

            if not links:
                continue

            already_visited = self.cache_service.set_contains_many(bwd_vis, links)
            new_links = [
                lnk
                for lnk, seen in zip(links, already_visited, strict=False)
                if not seen
            ]

            if not new_links:
                continue

            in_fwd = self.cache_service.set_contains_many(fwd_vis, new_links)
            self.cache_service.set_add_many(bwd_vis, new_links)
            self.cache_service.hash_set_many(bwd_par, {lnk: page for lnk in new_links})

            self.queue_service.push_batch(
                bwd_q, [{"page": lnk, "depth": depth + 1} for lnk in new_links]
            )

            for link, is_meeting in zip(new_links, in_fwd, strict=False):
                if is_meeting:
                    meeting_candidates.append(link)

        if meeting_candidates:
            return self._pick_shortest(meeting_candidates, fwd_par, bwd_par)
        return None

    def _pick_shortest(self, candidates: list[str], fwd_par: str, bwd_par: str) -> str:
        best = candidates[0]
        best_len = float("inf")
        for candidate in candidates:
            fwd_path = self._reconstruct_path(candidate, fwd_par)
            bwd_chain = self._reconstruct_bwd_chain(candidate, bwd_par)
            total = len(fwd_path) + len(bwd_chain)
            if total < best_len:
                best_len = total
                best = candidate
        return best

    def _reconstruct_path(self, node: str, parent_hash_key: str) -> list[str]:
        """Reconstruct forward path from start to node via parent hash."""
        path = [node]
        while True:
            parent = self.cache_service.hash_get(parent_hash_key, path[-1])
            if parent is None:
                break
            path.append(parent)
        path.reverse()
        return path

    def _reconstruct_bwd_chain(self, node: str, bwd_par: str) -> list[str]:
        """Reconstruct the chain from meeting node toward end_page via backward parent hash."""
        chain: list[str] = []
        current = node
        while True:
            child = self.cache_service.hash_get(bwd_par, current)
            if child is None:
                break
            chain.append(child)
            current = child
        return chain

    def _reconstruct_bidir_path(
        self,
        meeting: str,
        start_page: str,
        end_page: str,
        fwd_par: str,
        bwd_par: str,
    ) -> list[str]:
        """Stitch forward path + backward chain together."""
        fwd = self._reconstruct_path(meeting, fwd_par)
        bwd = self._reconstruct_bwd_chain(meeting, bwd_par)
        return fwd + bwd
