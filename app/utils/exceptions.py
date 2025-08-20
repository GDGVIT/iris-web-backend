class IrisBaseException(Exception):
    """Base exception for all Iris application exceptions."""

    def __init__(self, message: str = None, code: str = None):
        self.message = message or "An application error occurred"
        self.code = code or self.__class__.__name__
        super().__init__(self.message)


class WikipediaError(IrisBaseException):
    """Base exception for Wikipedia-related errors."""

    def __init__(self, message: str = None, page_title: str = None):
        self.page_title = page_title
        if not message and page_title:
            message = f"Wikipedia error for page '{page_title}'"
        super().__init__(message, "WIKIPEDIA_ERROR")


class WikipediaPageNotFoundError(WikipediaError):
    """Raised when a Wikipedia page is not found."""

    def __init__(self, page_title: str):
        message = f"Wikipedia page '{page_title}' not found"
        super().__init__(message, page_title)
        self.code = "WIKIPEDIA_PAGE_NOT_FOUND"


class WikipediaAPIError(WikipediaError):
    """Raised when Wikipedia API request fails."""

    def __init__(self, message: str = None, status_code: int = None):
        self.status_code = status_code
        if not message:
            message = f"Wikipedia API request failed"
            if status_code:
                message += f" (status {status_code})"
        super().__init__(message)
        self.code = "WIKIPEDIA_API_ERROR"


class PathFindingError(IrisBaseException):
    """Base exception for path finding errors."""

    def __init__(
        self, message: str = None, start_page: str = None, end_page: str = None
    ):
        self.start_page = start_page
        self.end_page = end_page
        if not message and start_page and end_page:
            message = f"Pathfinding error: {start_page} -> {end_page}"
        super().__init__(message, "PATHFINDING_ERROR")


class PathNotFoundError(PathFindingError):
    """Raised when no path is found between two pages."""

    def __init__(self, start_page: str, end_page: str, max_depth: int = None):
        message = f"No path found from '{start_page}' to '{end_page}'"
        if max_depth:
            message += f" within {max_depth} steps"
        super().__init__(message, start_page, end_page)
        self.max_depth = max_depth
        self.code = "PATH_NOT_FOUND"


class InvalidPageError(PathFindingError):
    """Raised when an invalid page is provided."""

    def __init__(self, message: str = None, page_title: str = None):
        self.page_title = page_title
        if not message:
            if page_title:
                message = f"Invalid page: '{page_title}'"
            else:
                message = "Invalid page provided"
        super().__init__(message)
        self.code = "INVALID_PAGE"


class DisambiguationPageError(PathFindingError):
    """Raised when a disambiguation page is used as a target."""

    def __init__(self, page_title: str, resolved_title: str = None):
        self.page_title = page_title
        self.resolved_title = resolved_title

        if resolved_title and resolved_title != page_title:
            message = f"'{page_title}' redirects to disambiguation page '{resolved_title}'. Please specify a more specific page."
        else:
            message = f"'{page_title}' is a disambiguation page. Please specify a more specific page."

        super().__init__(message, page_title, resolved_title)
        self.code = "DISAMBIGUATION_PAGE"


class CacheError(IrisBaseException):
    """Base exception for cache-related errors."""

    def __init__(self, message: str = None, operation: str = None):
        self.operation = operation
        if not message:
            message = "Cache operation failed"
            if operation:
                message = f"Cache {operation} operation failed"
        super().__init__(message, "CACHE_ERROR")


class CacheConnectionError(CacheError):
    """Raised when Redis connection fails."""

    def __init__(self, message: str = None):
        if not message:
            message = "Redis connection failed"
        super().__init__(message, "connection")
        self.code = "CACHE_CONNECTION_ERROR"


class TaskError(IrisBaseException):
    """Base exception for task-related errors."""

    def __init__(self, message: str = None, task_id: str = None):
        self.task_id = task_id
        if not message:
            message = "Task execution failed"
            if task_id:
                message = f"Task {task_id} failed"
        super().__init__(message, "TASK_ERROR")


class TaskTimeoutError(TaskError):
    """Raised when a task times out."""

    def __init__(self, task_id: str = None, timeout: int = None):
        message = "Task timed out"
        if task_id:
            message = f"Task {task_id} timed out"
        if timeout:
            message += f" after {timeout} seconds"
        super().__init__(message, task_id)
        self.timeout = timeout
        self.code = "TASK_TIMEOUT"


class ConfigurationError(IrisBaseException):
    """Raised when configuration is invalid or missing."""

    def __init__(self, message: str = None, config_key: str = None):
        self.config_key = config_key
        if not message:
            if config_key:
                message = f"Invalid configuration for '{config_key}'"
            else:
                message = "Configuration error"
        super().__init__(message, "CONFIGURATION_ERROR")
