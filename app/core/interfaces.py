from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any


class CacheServiceInterface(ABC):
    """Abstract interface for cache operations."""

    @abstractmethod
    def get(self, key: str) -> Any | None:
        """Get value from cache by key."""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache with optional TTL."""
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete key from cache."""
        pass

    @abstractmethod
    def delete_many(self, keys: list[str]) -> None:
        """Delete multiple keys atomically."""
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        pass

    @abstractmethod
    def clear_pattern(self, pattern: str) -> int:
        """Clear all keys matching a pattern. Returns count of deleted keys."""
        pass

    @abstractmethod
    def ping(self) -> bool:
        """Check connectivity. Returns True if reachable."""
        pass

    # --- Set operations ---

    @abstractmethod
    def set_add(self, key: str, value: str) -> None:
        """Add a value to a set."""
        pass

    @abstractmethod
    def set_add_many(self, key: str, values: list[str]) -> None:
        """Add multiple values to a set in a single round-trip."""
        pass

    @abstractmethod
    def set_contains(self, key: str, value: str) -> bool:
        """Return True if value is a member of the set."""
        pass

    @abstractmethod
    def set_contains_many(self, key: str, values: list[str]) -> list[bool]:
        """Return membership booleans for each value in a single round-trip."""
        pass

    # --- Hash operations ---

    @abstractmethod
    def hash_set(self, key: str, field: str, value: str) -> None:
        """Set a field in a hash."""
        pass

    @abstractmethod
    def hash_set_many(self, key: str, mapping: dict[str, str]) -> None:
        """Set multiple fields in a hash in a single round-trip."""
        pass

    @abstractmethod
    def hash_get(self, key: str, field: str) -> str | None:
        """Get a field from a hash. Returns None if missing."""
        pass


class WikipediaClientInterface(ABC):
    """Abstract interface for Wikipedia API operations."""

    @abstractmethod
    def get_links_bulk(
        self,
        page_titles: list[str],
        on_page_fetched: Callable[[str, list[str]], None] | None = None,
    ) -> dict[str, list[str]]:
        """Get links for multiple pages in bulk.

        Args:
            page_titles: Pages to fetch links for.
            on_page_fetched: Optional callback fired as soon as each page's
                links are available (cache hit or network response).  May be
                called from worker threads — must be thread-safe.
        """
        pass

    @abstractmethod
    def get_backlinks_bulk(
        self,
        page_titles: list[str],
        on_page_fetched: Callable[[str, list[str]], None] | None = None,
    ) -> dict[str, list[str]]:
        """Get backlinks (pages that link TO) for multiple pages in bulk.

        Args:
            page_titles: Pages to fetch backlinks for.
            on_page_fetched: Optional callback fired as soon as each page's
                backlinks are available.  May be called from worker threads —
                must be thread-safe.
        """
        pass

    @abstractmethod
    def page_exists(self, page_title: str) -> bool:
        """Check if a Wikipedia page exists."""
        pass

    @abstractmethod
    def get_page_with_redirect_info(self, page_title: str) -> dict | None:
        """Get page info including redirect and disambiguation details."""
        pass

    @abstractmethod
    def get_page_info(self, page_title: str) -> dict | None:
        """Get basic page information."""
        pass


class PathFinderInterface(ABC):
    """Abstract interface for path finding algorithms."""

    @abstractmethod
    def find_path(self, start_page: str, end_page: str) -> dict[str, Any]:
        """
        Find a path between two pages using BFS.

        Returns the first path found — not guaranteed to be the globally
        shortest due to Wikipedia's 500-link-per-page API cap, which may
        cause BFS to miss some outgoing links for high-connectivity pages.

        Returns:
            Dict with keys:
            - 'path': list[str] - The path from start to end
            - 'nodes_explored': int - Number of nodes explored during search
        """
        pass


class QueueInterface(ABC):
    """Abstract interface for queue operations."""

    @abstractmethod
    def push(self, queue_name: str, item: Any) -> None:
        """Push item to queue."""
        pass

    @abstractmethod
    def pop(self, queue_name: str) -> Any | None:
        """Pop item from queue."""
        pass

    @abstractmethod
    def length(self, queue_name: str) -> int:
        """Get queue length."""
        pass

    @abstractmethod
    def clear(self, queue_name: str) -> None:
        """Clear all items from queue."""
        pass

    @abstractmethod
    def push_batch(self, queue_name: str, items: list[Any]) -> None:
        """Push multiple items to queue efficiently."""
        pass

    @abstractmethod
    def pop_batch(self, queue_name: str, count: int) -> list[Any]:
        """Pop multiple items from queue efficiently."""
        pass
