from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial

import requests
from flask import current_app

from app.core.interfaces import CacheServiceInterface, WikipediaClientInterface
from app.utils.exceptions import WikipediaAPIError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class WikipediaClient(WikipediaClientInterface):
    """Wikipedia API client for fetching page links and information."""

    def __init__(
        self,
        cache_service: CacheServiceInterface | None = None,
        session: requests.Session | None = None,
        max_workers: int = 10,
        cache_ttl: int = 86400,  # 24 hours
        api_timeout: int = 15,
    ):
        self.session = session or requests.Session()
        self.cache_service = cache_service
        self.max_workers = max_workers
        self.cache_ttl = cache_ttl
        self.api_timeout = api_timeout
        self.base_url = "https://en.wikipedia.org/w/api.php"

        # Configure session
        self.session.headers.update(
            {
                "User-Agent": "Iris-Wikipedia-Pathfinder/1.0 (https://github.com/example/iris)"
            }
        )

    def _bulk_fetch(
        self,
        page_titles: list[str],
        cache_prefix: str,
        fetch_fn: Callable[..., dict[str, list[str]]],
        on_page_fetched: Callable[[str, list[str]], None] | None,
    ) -> dict[str, list[str]]:
        """Shared scaffolding: cache-check, thread-pool fetch, cache results.

        Args:
            page_titles: Wikipedia page titles to fetch.
            cache_prefix: Redis key prefix (e.g. ``"wiki_links"`` or
                ``"wiki_backlinks"``).
            fetch_fn: Callable that fetches a single page and returns
                ``{title: [links]}``.
            on_page_fetched: Optional callback fired per page (thread-safe).

        Returns:
            Dictionary mapping page titles to their link/backlink lists.
        """
        if not page_titles:
            return {}

        results: dict[str, list[str]] = {}
        uncached_titles: list[str] = []

        # Check cache first if cache service is available
        if self.cache_service:
            for title in page_titles:
                cache_key = f"{cache_prefix}:{title}"
                cached_links = self.cache_service.get(cache_key)
                if cached_links is not None:
                    results[title] = cached_links
                    logger.debug(f"Cache hit for page: {title}")
                    if on_page_fetched:
                        on_page_fetched(title, cached_links)
                else:
                    uncached_titles.append(title)

            logger.info(
                f"Cache hits: {len(results)}, Cache misses: {len(uncached_titles)}"
            )
        else:
            uncached_titles = page_titles

        # Fetch uncached titles from Wikipedia API using thread pool
        if uncached_titles:
            fresh_results: dict[str, list[str]] = {}

            # Read pagination config here (app context available), bind to fetch_fn
            # so threads don't need to access current_app themselves.
            max_paginate_calls = current_app.config.get(
                "WIKIPEDIA_MAX_PAGINATE_CALLS", 10
            )
            bound_fetch = partial(fetch_fn, max_paginate_calls=max_paginate_calls)

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_title = {
                    executor.submit(bound_fetch, title): title
                    for title in uncached_titles
                }
                for future in as_completed(future_to_title):
                    title = future_to_title[future]
                    try:
                        page_result = future.result()
                    except WikipediaAPIError:
                        raise
                    except Exception as e:
                        logger.error(f"Unexpected error fetching '{title}': {e}")
                        page_result = {title: []}
                    fresh_results.update(page_result)
                    if on_page_fetched:
                        on_page_fetched(title, page_result.get(title, []))

            # Cache the fresh results
            if self.cache_service:
                for title, links in fresh_results.items():
                    cache_key = f"{cache_prefix}:{title}"
                    self.cache_service.set(cache_key, links, ttl=self.cache_ttl)
                    logger.debug(f"Cached {cache_prefix} for page: {title}")

            results.update(fresh_results)

        return results

    def get_links_bulk(
        self,
        page_titles: list[str],
        on_page_fetched: Callable[[str, list[str]], None] | None = None,
    ) -> dict[str, list[str]]:
        """
        Fetches links for a list of pages using efficient bulk API requests with caching.

        Args:
            page_titles: List of Wikipedia page titles

        Returns:
            Dictionary mapping page titles to their links

        Raises:
            WikipediaAPIError: When API requests fail
        """
        return self._bulk_fetch(
            page_titles, "wiki_links", self._fetch_single_page, on_page_fetched
        )

    def get_backlinks_bulk(
        self,
        page_titles: list[str],
        on_page_fetched: Callable[[str, list[str]], None] | None = None,
    ) -> dict[str, list[str]]:
        """
        Fetches backlinks (pages that link TO each page) using bulk API requests with caching.

        Args:
            page_titles: List of Wikipedia page titles

        Returns:
            Dictionary mapping page titles to pages that link to them

        Raises:
            WikipediaAPIError: When API requests fail
        """
        return self._bulk_fetch(
            page_titles,
            "wiki_backlinks",
            self._fetch_backlinks_single_page,
            on_page_fetched,
        )

    def _fetch_single_page(
        self, title: str, max_paginate_calls: int = 10
    ) -> dict[str, list[str]]:
        """Fetch links for a single Wikipedia page with plcontinue pagination."""
        params: dict[str, str | int] = {
            "action": "query",
            "format": "json",
            "titles": title,
            "prop": "links",
            "pllimit": "max",
            "redirects": 1,
        }
        all_links: list[str] = []
        max_pages = max_paginate_calls
        calls = 0

        try:
            while calls < max_pages:
                response = self.session.get(
                    self.base_url, params=params, timeout=self.api_timeout
                )
                response.raise_for_status()
                data = response.json()
                query_data = data.get("query", {})
                page_links = self._parse_batch_response(query_data, [title])
                all_links.extend(page_links.get(title, []))
                calls += 1
                if "continue" not in data:
                    break
                params["plcontinue"] = data["continue"]["plcontinue"]
                params["continue"] = data["continue"]["continue"]
        except requests.RequestException as e:
            logger.error(f"Wikipedia API request failed for '{title}': {e}")
            raise WikipediaAPIError(f"API request failed: {e}")

        return {title: all_links}

    def _fetch_backlinks_single_page(
        self, title: str, max_paginate_calls: int = 10
    ) -> dict[str, list[str]]:
        """Fetch backlinks for a single Wikipedia page with blcontinue pagination.

        Uses ``list=backlinks`` which returns pages that link *to* ``title``.
        Only namespace-0 (article) backlinks are returned.
        """
        params: dict[str, str | int] = {
            "action": "query",
            "format": "json",
            "list": "backlinks",
            "bltitle": title,
            "bllimit": "max",
            "blnamespace": 0,
            "redirects": 1,
        }
        all_backlinks: list[str] = []
        max_pages = max_paginate_calls
        calls = 0

        try:
            while calls < max_pages:
                response = self.session.get(
                    self.base_url, params=params, timeout=self.api_timeout
                )
                response.raise_for_status()
                data = response.json()
                backlinks = data.get("query", {}).get("backlinks", [])
                all_backlinks.extend(
                    bl["title"]
                    for bl in backlinks
                    if ":" not in bl.get("title", "")
                    or bl.get("title", "").startswith("List of")
                )
                calls += 1
                if "continue" not in data:
                    break
                params["blcontinue"] = data["continue"]["blcontinue"]
                params["continue"] = data["continue"]["continue"]
        except requests.RequestException as e:
            logger.error(f"Wikipedia backlinks API request failed for '{title}': {e}")
            raise WikipediaAPIError(f"API request failed: {e}")

        return {title: all_backlinks}

    def _parse_batch_response(
        self, data: dict, original_batch: list[str]
    ) -> dict[str, list[str]]:
        """Parse Wikipedia API response and extract links."""
        results = {}

        # Handle redirects and normalization
        redirect_map = {item["from"]: item["to"] for item in data.get("redirects", [])}
        normalized_map = {
            item["from"]: item["to"] for item in data.get("normalized", [])
        }

        # Parse pages and extract links
        for _page_id, page_data in data.get("pages", {}).items():
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
            response = self.session.get(
                self.base_url, params=params, timeout=self.api_timeout
            )
            response.raise_for_status()
            data = response.json().get("query", {})

            pages = data.get("pages", {})
            for page_data in pages.values():
                return "missing" not in page_data

            return False
        except requests.RequestException as e:
            logger.error(f"Failed to check page existence for {page_title}: {e}")
            return False

    def get_page_with_redirect_info(self, page_title: str) -> dict | None:
        """
        Get page information including redirect details.

        Args:
            page_title: Wikipedia page title

        Returns:
            Dict with 'exists', 'final_title', 'was_redirected', 'is_disambiguation'
        """
        params = {
            "action": "query",
            "format": "json",
            "titles": page_title,
            "prop": "info|categories",
            "redirects": 1,
        }

        try:
            response = self.session.get(
                self.base_url, params=params, timeout=self.api_timeout
            )
            response.raise_for_status()
            data = response.json().get("query", {})

            # Check for redirects
            redirects = data.get("redirects", [])
            was_redirected = len(redirects) > 0
            final_title = page_title

            if was_redirected:
                # Find the final redirect target
                for redirect in redirects:
                    if redirect.get("from") == page_title:
                        final_title = redirect.get("to", page_title)
                        break

            # Check if page exists
            pages = data.get("pages", {})
            page_exists = False
            is_disambiguation = False

            for page_data in pages.values():
                if "missing" not in page_data:
                    page_exists = True
                    current_title = page_data.get("title", "")

                    # Check if it's a disambiguation page
                    if "(disambiguation)" in current_title.lower():
                        is_disambiguation = True
                    else:
                        # Check categories for disambiguation
                        categories = page_data.get("categories", [])
                        for category in categories:
                            cat_title = category.get("title", "").lower()
                            if "disambiguation" in cat_title:
                                is_disambiguation = True
                                break

            return {
                "exists": page_exists,
                "final_title": final_title,
                "was_redirected": was_redirected,
                "is_disambiguation": is_disambiguation,
                "original_title": page_title,
            }

        except requests.RequestException as e:
            logger.error(f"Failed to get page redirect info for {page_title}: {e}")
            return {
                "exists": False,
                "final_title": page_title,
                "was_redirected": False,
                "is_disambiguation": False,
                "original_title": page_title,
            }

    def get_page_info(self, page_title: str) -> dict | None:
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
            response = self.session.get(
                self.base_url, params=params, timeout=self.api_timeout
            )
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
