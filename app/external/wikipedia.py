import requests
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional
from app.core.interfaces import WikipediaClientInterface, CacheServiceInterface
from app.utils.exceptions import WikipediaAPIError, WikipediaPageNotFoundError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class WikipediaClient(WikipediaClientInterface):
    """Wikipedia API client for fetching page links and information."""

    def __init__(
        self,
        cache_service: Optional[CacheServiceInterface] = None,
        session: Optional[requests.Session] = None,
        max_workers: int = 10,
        cache_ttl: int = 86400,  # 24 hours
    ):
        self.session = session or requests.Session()
        self.cache_service = cache_service
        self.max_workers = max_workers
        self.cache_ttl = cache_ttl
        self.base_url = "https://en.wikipedia.org/w/api.php"

        # Configure session
        self.session.headers.update(
            {
                "User-Agent": "Iris-Wikipedia-Pathfinder/1.0 (https://github.com/example/iris)"
            }
        )

    def get_links_bulk(self, page_titles: List[str]) -> Dict[str, List[str]]:
        """
        Fetches links for a list of pages using efficient bulk API requests with caching.

        Args:
            page_titles: List of Wikipedia page titles

        Returns:
            Dictionary mapping page titles to their links

        Raises:
            WikipediaAPIError: When API requests fail
        """
        if not page_titles:
            return {}

        results = {}
        uncached_titles = []

        # Check cache first if cache service is available
        if self.cache_service:
            for title in page_titles:
                cache_key = f"wiki_links:{title}"
                cached_links = self.cache_service.get(cache_key)
                if cached_links is not None:
                    results[title] = cached_links
                    logger.debug(f"Cache hit for page: {title}")
                else:
                    uncached_titles.append(title)

            logger.info(
                f"Cache hits: {len(results)}, Cache misses: {len(uncached_titles)}"
            )
        else:
            uncached_titles = page_titles

        # Fetch uncached titles from Wikipedia API
        if uncached_titles:
            fresh_results = self._fetch_from_wikipedia(uncached_titles)

            # Cache the fresh results
            if self.cache_service:
                for title, links in fresh_results.items():
                    cache_key = f"wiki_links:{title}"
                    self.cache_service.set(cache_key, links, ttl=self.cache_ttl)
                    logger.debug(f"Cached links for page: {title}")

            results.update(fresh_results)

        return results

    def _fetch_from_wikipedia(self, page_titles: List[str]) -> Dict[str, List[str]]:
        """Fetch page links directly from Wikipedia API without caching."""
        results = {}

        # Group titles into batches of 50 (Wikipedia API limit)
        batches = [page_titles[i : i + 50] for i in range(0, len(page_titles), 50)]

        # Process batches in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            batch_results = list(executor.map(self._process_batch, batches))

        # Merge results from all batches
        for batch_result in batch_results:
            results.update(batch_result)

        return results

    def _process_batch(self, batch: List[str]) -> Dict[str, List[str]]:
        """Process a single batch of up to 50 titles using prop=links."""
        titles_param = "|".join(batch)
        params = {
            "action": "query",
            "format": "json",
            "titles": titles_param,
            "prop": "links",
            "pllimit": "max",
            "redirects": 1,
        }

        try:
            response = self.session.get(self.base_url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json().get("query", {})
        except requests.RequestException as e:
            logger.error(f"Wikipedia API request failed for batch: {e}")
            raise WikipediaAPIError(f"API request failed: {e}")

        return self._parse_batch_response(data, batch)

    def _parse_batch_response(
        self, data: dict, original_batch: List[str]
    ) -> Dict[str, List[str]]:
        """Parse Wikipedia API response and extract links."""
        results = {}

        # Handle redirects and normalization
        redirect_map = {item["from"]: item["to"] for item in data.get("redirects", [])}
        normalized_map = {
            item["from"]: item["to"] for item in data.get("normalized", [])
        }

        # Parse pages and extract links
        for page_id, page_data in data.get("pages", {}).items():
            title = page_data.get("title")
            if not title or "missing" in page_data:
                continue

            # Extract article links (exclude namespace links like "Category:", "File:", etc.)
            links = page_data.get("links", [])
            article_links = [
                link["title"]
                for link in links
                if ":" not in link["title"] or link["title"].startswith("List of")
            ]

            results[title] = article_links

            # Map results back to original titles that were redirected/normalized
            for original_title, final_title in redirect_map.items():
                if final_title == title and original_title in original_batch:
                    results[original_title] = article_links

            for original_title, final_title in normalized_map.items():
                if final_title == title and original_title in original_batch:
                    results[original_title] = article_links

        # Ensure all batch titles have results (empty list for missing pages)
        for title in original_batch:
            if title not in results:
                results[title] = []
                logger.warning(f"No links found for page: {title}")

        return results

    def page_exists(self, page_title: str) -> bool:
        """
        Check if a Wikipedia page exists.

        Args:
            page_title: Wikipedia page title

        Returns:
            True if page exists, False otherwise
        """
        params = {
            "action": "query",
            "format": "json",
            "titles": page_title,
            "redirects": 1,
        }

        try:
            response = self.session.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json().get("query", {})

            pages = data.get("pages", {})
            for page_data in pages.values():
                return "missing" not in page_data

            return False
        except requests.RequestException as e:
            logger.error(f"Failed to check page existence for {page_title}: {e}")
            return False

    def get_page_info(self, page_title: str) -> Optional[dict]:
        """
        Get basic information about a Wikipedia page.

        Args:
            page_title: Wikipedia page title

        Returns:
            Dictionary with page info or None if page doesn't exist
        """
        params = {
            "action": "query",
            "format": "json",
            "titles": page_title,
            "prop": "info",
            "redirects": 1,
        }

        try:
            response = self.session.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json().get("query", {})

            pages = data.get("pages", {})
            for page_data in pages.values():
                if "missing" not in page_data:
                    return {
                        "title": page_data.get("title"),
                        "page_id": page_data.get("pageid"),
                        "last_modified": page_data.get("touched"),
                    }

            return None
        except requests.RequestException as e:
            logger.error(f"Failed to get page info for {page_title}: {e}")
            return None
