from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class CacheServiceInterface(ABC):
    """Abstract interface for cache operations."""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache by key."""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: int = None) -> None:
        """Set value in cache with optional TTL."""
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete key from cache."""
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        pass


class WikipediaClientInterface(ABC):
    """Abstract interface for Wikipedia API operations."""

    @abstractmethod
    def get_links_bulk(self, page_titles: List[str]) -> Dict[str, List[str]]:
        """Get links for multiple pages in bulk."""
        pass

    @abstractmethod
    def page_exists(self, page_title: str) -> bool:
        """Check if a Wikipedia page exists."""
        pass


class PathFinderInterface(ABC):
    """Abstract interface for path finding algorithms."""

    @abstractmethod
    def find_shortest_path(self, start_page: str, end_page: str) -> Dict[str, Any]:
        """
        Find shortest path between two pages.

        Returns:
            Dict with keys:
            - 'path': List[str] - The path from start to end
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
    def pop(self, queue_name: str) -> Optional[Any]:
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
