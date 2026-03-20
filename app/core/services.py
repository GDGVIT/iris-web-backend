import time

from flask import current_app

from app.core.interfaces import (
    CacheServiceInterface,
    PathFinderInterface,
    WikipediaClientInterface,
)
from app.core.models import (
    PathResult,
    SearchRequest,
    WikipediaPage,
)
from app.utils.constants import CACHE_PREFIX_PAGE_INFO, CACHE_PREFIX_PATH
from app.utils.exceptions import (
    DisambiguationPageError,
    InvalidPageError,
)
from app.utils.logging import get_logger

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
        Find a path between two Wikipedia pages using BFS.

        Args:
            request: Search request with start and end pages

        Returns:
            PathResult with the path and metadata

        Raises:
            InvalidPageError: When request is invalid or pages don't exist
            PathNotFoundError: When no path exists between pages
        """
        if not request.validate():
            raise InvalidPageError("Invalid search request")

        # Check cache first
        cache_key = f"{CACHE_PREFIX_PATH}:{request.start_page}:{request.end_page}"
        cached_result = self.cache_service.get(cache_key)
        if cached_result:
            logger.info(
                "path_cache_hit",
                extra={"start_page": request.start_page, "end_page": request.end_page},
            )
            return PathResult(**cached_result)

        # Perform pathfinding
        start_time = time.time()
        try:
            path_result = self.path_finder.find_path(
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
                cache_key,
                {
                    "path": result.path,
                    "length": result.length,
                    "start_page": result.start_page,
                    "end_page": result.end_page,
                    "search_time": result.search_time,
                    "nodes_explored": result.nodes_explored,
                },
                ttl=current_app.config.get("CACHE_PATH_TTL", 3600),
            )

            logger.info(
                "path_found",
                extra={
                    "start_page": request.start_page,
                    "end_page": request.end_page,
                    "path_length": len(path),
                    "search_time": round(search_time, 3),
                },
            )
            return result

        except Exception as e:
            search_time = time.time() - start_time
            logger.error(
                "pathfinding_failed",
                extra={
                    "start_page": request.start_page,
                    "end_page": request.end_page,
                    "search_time": round(search_time, 3),
                    "error": str(e),
                },
            )
            raise

    def validate_pages(self, start_page: str, end_page: str) -> tuple[bool, bool, dict]:
        """
        Validate that both pages exist on Wikipedia and check for disambiguation pages.

        Args:
            start_page: Starting page title
            end_page: Target page title

        Returns:
            Tuple of (start_exists, end_exists, validation_details)

        Raises:
            DisambiguationPageError: When end page is a disambiguation page
        """
        # Get detailed info for both pages
        _default = {
            "exists": False,
            "final_title": None,
            "was_redirected": False,
            "is_disambiguation": False,
        }
        start_info = (
            self.wikipedia_client.get_page_with_redirect_info(start_page) or _default
        )
        end_info = (
            self.wikipedia_client.get_page_with_redirect_info(end_page) or _default
        )

        start_exists = start_info.get("exists", False)
        end_exists = end_info.get("exists", False)

        validation_details = {
            "start_page": {
                "original": start_page,
                "final_title": start_info.get("final_title", start_page),
                "was_redirected": start_info.get("was_redirected", False),
                "is_disambiguation": start_info.get("is_disambiguation", False),
                "exists": start_exists,
            },
            "end_page": {
                "original": end_page,
                "final_title": end_info.get("final_title", end_page),
                "was_redirected": end_info.get("was_redirected", False),
                "is_disambiguation": end_info.get("is_disambiguation", False),
                "exists": end_exists,
            },
        }

        # Check if end page is disambiguation - this should fail
        if end_exists and end_info.get("is_disambiguation", False):
            final_title = end_info.get("final_title", end_page)
            raise DisambiguationPageError(end_page, final_title)

        # Note: We allow start page to be disambiguation as it might have useful links

        return start_exists, end_exists, validation_details


class WikipediaService:
    """Service for Wikipedia page operations."""

    def __init__(
        self,
        wikipedia_client: WikipediaClientInterface,
        cache_service: CacheServiceInterface,
    ):
        self.wikipedia_client = wikipedia_client
        self.cache_service = cache_service

    def get_page_info(self, page_title: str) -> WikipediaPage | None:
        """Get information about a Wikipedia page."""
        if not page_title or not page_title.strip():
            raise InvalidPageError("Page title cannot be empty")

        # Check cache first
        cache_key = f"{CACHE_PREFIX_PAGE_INFO}:{page_title}"
        cached_info = self.cache_service.get(cache_key)
        if cached_info:
            return WikipediaPage(**cached_info)

        # Get page info from Wikipedia
        page_info = self.wikipedia_client.get_page_info(page_title)
        if not page_info:
            return None

        page = WikipediaPage(
            title=page_info.get("title") or page_title,
            page_id=page_info.get("page_id"),
            last_modified=page_info.get("last_modified"),
        )

        # Cache the result
        self.cache_service.set(
            cache_key,
            {
                "title": page.title,
                "page_id": page.page_id,
                "last_modified": page.last_modified,
                "links": page.links,
            },
            ttl=current_app.config.get("CACHE_PAGE_TTL", 7200),
        )

        return page


class CacheManagementService:
    """Service for cache management operations."""

    def __init__(self, cache_service: CacheServiceInterface):
        self.cache_service = cache_service

    def clear_cache_pattern(self, pattern: str) -> int:
        """Clear all cache entries matching a pattern."""
        try:
            return self.cache_service.clear_pattern(pattern)
        except Exception as e:
            logger.error("cache_clear_pattern_failed", extra={"pattern": pattern, "error": str(e)})
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
            logger.error("cache_stats_failed", extra={"error": str(e)})
            return {"status": "error", "message": str(e)}
