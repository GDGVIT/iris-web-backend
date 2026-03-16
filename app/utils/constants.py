# ---------------------------------------------------------------------------
# Redis key prefixes — BFS session state (namespaced by UUID per search)
# Format: f"{PREFIX}:{session_id}"
# ---------------------------------------------------------------------------
BFS_QUEUE_PREFIX = "bfs_queue"
BFS_VISITED_PREFIX = "bfs_visited"
BFS_PARENT_PREFIX = "bfs_parent"

BFS_FWD_QUEUE_PREFIX = "bfs_fwd_queue"
BFS_BWD_QUEUE_PREFIX = "bfs_bwd_queue"
BFS_FWD_VISITED_PREFIX = "bfs_fwd_visited"
BFS_BWD_VISITED_PREFIX = "bfs_bwd_visited"
BFS_FWD_PARENT_PREFIX = "bfs_fwd_parent"
BFS_BWD_PARENT_PREFIX = "bfs_bwd_parent"

# Shared prefix for all BFS session keys — used for pattern matching
BFS_KEY_PREFIX = "bfs_"

# Pattern used by the periodic cleanup task to wipe all BFS session keys
BFS_CACHE_CLEANUP_PATTERN = "bfs_*"

# ---------------------------------------------------------------------------
# Cache key prefixes — persistent Wikipedia / pathfinding results
# Keys are built as f"{PREFIX}:{identifier}"
# ---------------------------------------------------------------------------
CACHE_PREFIX_WIKI_LINKS = "wiki_links"
CACHE_PREFIX_WIKI_BACKLINKS = "wiki_backlinks"
CACHE_PREFIX_PATH = "path"
CACHE_PREFIX_PAGE_INFO = "page_info"

# Valid prefixes accepted by the /cache/clear endpoint
ALLOWED_CACHE_PREFIXES = (
    BFS_KEY_PREFIX,  # bfs_queue:*, bfs_visited:*, bfs_fwd_*:*, etc.
    f"{CACHE_PREFIX_WIKI_LINKS}:",
    f"{CACHE_PREFIX_WIKI_BACKLINKS}:",
    f"{CACHE_PREFIX_PATH}:",
    f"{CACHE_PREFIX_PAGE_INFO}:",
)

# ---------------------------------------------------------------------------
# Celery queue names
# ---------------------------------------------------------------------------
QUEUE_PATHFINDING = "pathfinding"
QUEUE_HEALTH = "health"
QUEUE_MAINTENANCE = "maintenance"

# ---------------------------------------------------------------------------
# Celery task state strings
# PROGRESS is a custom state emitted during pathfinding execution.
# The rest are standard Celery states used as string literals across files.
# ---------------------------------------------------------------------------
CELERY_STATE_PROGRESS = "PROGRESS"
CELERY_STATE_SUCCESS = "SUCCESS"
CELERY_STATE_FAILURE = "FAILURE"
CELERY_STATE_RETRY = "RETRY"
CELERY_STATE_REVOKED = "REVOKED"

# ---------------------------------------------------------------------------
# Algorithm identifiers
# ---------------------------------------------------------------------------
ALGORITHM_BIDIRECTIONAL = "bidirectional"
ALGORITHM_BFS = "bfs"

# ---------------------------------------------------------------------------
# Task error codes (returned in the "code" field of FAILURE responses)
# ---------------------------------------------------------------------------
ERROR_INVALID_REQUEST = "INVALID_REQUEST"
ERROR_DISAMBIGUATION_PAGE = "DISAMBIGUATION_PAGE"
ERROR_PAGE_NOT_FOUND = "PAGE_NOT_FOUND"
ERROR_PATH_NOT_FOUND = "PATH_NOT_FOUND"
ERROR_INVALID_PAGE = "INVALID_PAGE"
ERROR_MAX_RETRIES_EXCEEDED = "MAX_RETRIES_EXCEEDED"
ERROR_INTERNAL_ERROR = "INTERNAL_ERROR"

# ---------------------------------------------------------------------------
# Celery Beat periodic task identifiers
# ---------------------------------------------------------------------------
PERIODIC_TASK_CLEANUP_BFS = "cleanup-bfs-cache"
PERIODIC_TASK_HEALTH_CHECK = "health-check"

# ---------------------------------------------------------------------------
# Celery task fully-qualified names (used in task routing and beat schedule)
# ---------------------------------------------------------------------------
TASK_FQN_FIND_PATH = "app.infrastructure.tasks.find_path_task"
TASK_FQN_HEALTH_CHECK = "app.infrastructure.tasks.health_check_task"
TASK_FQN_CACHE_CLEANUP = "app.infrastructure.tasks.cache_cleanup_task"

# ---------------------------------------------------------------------------
# Wikipedia API
# ---------------------------------------------------------------------------
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_USER_AGENT = "Iris-Wikipedia-Pathfinder/1.0 (https://github.com/mdhishaamakhtar/iris-web-backend)"

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
HEALTH_CHECK_CACHE_KEY = "health_check"
