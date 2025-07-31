import time
from typing import List, Optional
from app.core.interfaces import (
    PathFinderInterface,
    WikipediaClientInterface,
    CacheServiceInterface,
)
from app.core.models import (
    PathResult,
    ExploreResult,
    SearchRequest,
    ExploreRequest,
    WikipediaPage,
)
from app.utils.exceptions import (
    PathNotFoundError,
    InvalidPageError,
    WikipediaPageNotFoundError,
)
from app.utils.logging import get_logger
import networkx as nx

logger = get_logger(__name__)


class PathFindingService:
    """Service for orchestrating pathfinding operations."""

    def __init__(
        self,
        path_finder: PathFinderInterface,
        cache_service: CacheServiceInterface,
        wikipedia_client: WikipediaClientInterface,
    ):
        self.path_finder = path_finder
        self.cache_service = cache_service
        self.wikipedia_client = wikipedia_client

    def find_path(self, request: SearchRequest) -> PathResult:
        """
        Find the shortest path between two Wikipedia pages.

        Args:
            request: Search request with start and end pages

        Returns:
            PathResult with the shortest path and metadata

        Raises:
            InvalidPageError: When request is invalid or pages don't exist
            PathNotFoundError: When no path exists between pages
        """
        if not request.validate():
            raise InvalidPageError("Invalid search request")

        # Check cache first
        cache_key = f"path:{request.start_page}:{request.end_page}"
        cached_result = self.cache_service.get(cache_key)
        if cached_result:
            logger.info(
                f"Path found in cache: {request.start_page} -> {request.end_page}"
            )
            return PathResult(**cached_result)

        # Perform pathfinding
        start_time = time.time()
        try:
            path_result = self.path_finder.find_shortest_path(
                request.start_page, request.end_page
            )
            search_time = time.time() - start_time

            path = path_result["path"]
            nodes_explored = path_result["nodes_explored"]

            result = PathResult(
                path=path,
                length=len(path),
                start_page=request.start_page,
                end_page=request.end_page,
                search_time=search_time,
                nodes_explored=nodes_explored,
            )

            # Cache the result
            self.cache_service.set(
                cache_key, result.__dict__, ttl=3600
            )  # Cache for 1 hour

            logger.info(
                f"Path found: {request.start_page} -> {request.end_page} (length: {len(path)}, time: {search_time:.2f}s)"
            )
            return result

        except Exception as e:
            search_time = time.time() - start_time
            logger.error(
                f"Pathfinding failed: {request.start_page} -> {request.end_page} (time: {search_time:.2f}s): {e}"
            )
            raise

    def validate_pages(self, start_page: str, end_page: str) -> tuple[bool, bool]:
        """
        Validate that both pages exist on Wikipedia.

        Returns:
            Tuple of (start_exists, end_exists)
        """
        start_exists = self.wikipedia_client.page_exists(start_page)
        end_exists = self.wikipedia_client.page_exists(end_page)
        return start_exists, end_exists


class ExploreService:
    """Service for exploring Wikipedia page connections."""

    def __init__(
        self,
        wikipedia_client: WikipediaClientInterface,
        cache_service: CacheServiceInterface,
    ):
        self.wikipedia_client = wikipedia_client
        self.cache_service = cache_service

    def explore_page(self, request: ExploreRequest) -> ExploreResult:
        """
        Explore connections from a Wikipedia page.

        Args:
            request: Explore request with start page and options

        Returns:
            ExploreResult with nodes and edges for visualization

        Raises:
            InvalidPageError: When request is invalid or page doesn't exist
        """
        if not request.validate():
            raise InvalidPageError("Invalid explore request")

        # Check cache first
        cache_key = f"explore:{request.start_page}:{request.max_links}"
        cached_result = self.cache_service.get(cache_key)
        if cached_result:
            logger.info(f"Explore result found in cache: {request.start_page}")
            return ExploreResult(**cached_result)

        # Check if page exists
        if not self.wikipedia_client.page_exists(request.start_page):
            raise InvalidPageError(f"Page '{request.start_page}' does not exist")

        # Get links for the page
        try:
            links_data = self.wikipedia_client.get_links_bulk([request.start_page])
            all_links = links_data.get(request.start_page, [])

            if not all_links:
                logger.warning(f"No links found for page: {request.start_page}")
                return ExploreResult(
                    start_page=request.start_page,
                    nodes=[request.start_page],
                    edges=[],
                    total_links=0,
                )

            # Limit links for visualization
            limited_links = all_links[: request.max_links]

            # Generate graph data
            result = self._generate_explore_graph(
                request.start_page, limited_links, len(all_links)
            )

            # Cache the result
            self.cache_service.set(
                cache_key, result.__dict__, ttl=1800
            )  # Cache for 30 minutes

            logger.info(
                f"Explore completed: {request.start_page} ({len(limited_links)} links shown)"
            )
            return result

        except Exception as e:
            logger.error(f"Explore failed for {request.start_page}: {e}")
            raise

    def _generate_explore_graph(
        self, start_page: str, links: List[str], total_links: int
    ) -> ExploreResult:
        """Generate graph data for visualization."""
        # Create graph
        G = nx.Graph()
        G.add_node(start_page)

        nodes = [start_page]
        edges = []

        for link in links:
            G.add_node(link)
            G.add_edge(start_page, link)
            nodes.append(link)
            edges.append((start_page, link))

        return ExploreResult(
            start_page=start_page, nodes=nodes, edges=edges, total_links=total_links
        )


class WikipediaService:
    """Service for Wikipedia page operations."""

    def __init__(
        self,
        wikipedia_client: WikipediaClientInterface,
        cache_service: CacheServiceInterface,
    ):
        self.wikipedia_client = wikipedia_client
        self.cache_service = cache_service

    def get_page_info(self, page_title: str) -> Optional[WikipediaPage]:
        """Get information about a Wikipedia page."""
        if not page_title or not page_title.strip():
            raise InvalidPageError("Page title cannot be empty")

        # Check cache first
        cache_key = f"page_info:{page_title}"
        cached_info = self.cache_service.get(cache_key)
        if cached_info:
            return WikipediaPage(**cached_info)

        # Get page info from Wikipedia
        page_info = self.wikipedia_client.get_page_info(page_title)
        if not page_info:
            return None

        page = WikipediaPage(
            title=page_info.get("title"),
            page_id=page_info.get("page_id"),
            last_modified=page_info.get("last_modified"),
        )

        # Cache the result
        self.cache_service.set(cache_key, page.__dict__, ttl=7200)  # Cache for 2 hours

        return page

    def search_pages(self, query: str, limit: int = 10) -> List[str]:
        """Search for Wikipedia pages by title."""
        # This would implement Wikipedia search API
        # For now, return empty list as it's not in the original scope
        return []


class CacheManagementService:
    """Service for cache management operations."""

    def __init__(self, cache_service: CacheServiceInterface):
        self.cache_service = cache_service

    def clear_cache_pattern(self, pattern: str) -> int:
        """Clear all cache entries matching a pattern."""
        try:
            if hasattr(self.cache_service, "clear_pattern"):
                return self.cache_service.clear_pattern(pattern)
            else:
                logger.warning("Cache service doesn't support pattern clearing")
                return 0
        except Exception as e:
            logger.error(f"Failed to clear cache pattern {pattern}: {e}")
            return 0

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        try:
            # This would be implemented based on the specific cache backend
            return {
                "status": "available",
                "message": "Cache statistics not implemented",
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"status": "error", "message": str(e)}
