from dataclasses import dataclass
from enum import Enum


class TaskStatus(Enum):
    """Task status enumeration."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    RETRY = "RETRY"


@dataclass
class PathResult:
    """Result of a pathfinding operation."""

    path: list[str]
    length: int
    start_page: str
    end_page: str
    search_time: float | None = None
    nodes_explored: int | None = None

    @property
    def is_valid(self) -> bool:
        """Check if the path result is valid."""
        return (
            len(self.path) >= 2
            and self.path[0] == self.start_page
            and self.path[-1] == self.end_page
            and self.length == len(self.path)
        )


@dataclass
class ExploreResult:
    """Result of an explore operation."""

    start_page: str
    nodes: list[str]
    edges: list[tuple]
    total_links: int

    @property
    def is_valid(self) -> bool:
        """Check if the explore result is valid."""
        return (
            self.start_page in self.nodes
            and len(self.nodes) > 0
            and self.total_links >= 0
        )


@dataclass
class TaskInfo:
    """Information about a background task."""

    task_id: str
    status: TaskStatus
    result: dict | None = None
    error: str | None = None
    progress: dict | None = None
    created_at: str | None = None
    updated_at: str | None = None


@dataclass
class SearchRequest:
    """Request for pathfinding search."""

    start_page: str
    end_page: str
    max_depth: int | None = None
    algorithm: str | None = "bfs"

    def validate(self) -> bool:
        """Validate the search request."""
        return (
            bool(self.start_page and self.start_page.strip())
            and bool(self.end_page and self.end_page.strip())
            and self.start_page != self.end_page
        )


@dataclass
class ExploreRequest:
    """Request for page exploration."""

    start_page: str
    max_links: int | None = None

    def validate(self) -> bool:
        """Validate the explore request."""
        return bool(self.start_page and self.start_page.strip())


@dataclass
class WikipediaPage:
    """Represents a Wikipedia page."""

    title: str
    page_id: int | None = None
    last_modified: str | None = None
    links: list[str] | None = None

    @property
    def is_valid(self) -> bool:
        """Check if the page is valid."""
        return bool(self.title and self.title.strip())


@dataclass
class CacheStats:
    """Cache statistics."""

    total_keys: int
    memory_usage: int | None = None
    hit_rate: float | None = None
    miss_rate: float | None = None


@dataclass
class HealthStatus:
    """System health status."""

    status: str  # "healthy", "degraded", "unhealthy"
    redis_status: str
    celery_status: str
    wikipedia_api_status: str
    timestamp: str
    details: dict | None = None
