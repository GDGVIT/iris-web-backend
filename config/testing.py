from config.base import BaseConfig


class TestingConfig(BaseConfig):
    """Testing-specific configuration."""

    DEBUG = False
    TESTING = True

    # Use separate Redis database for testing
    REDIS_URL = "redis://localhost:6379/1"

    # Fast timeouts for testing
    WIKIPEDIA_API_TIMEOUT = 5

    # Small cache TTL for testing
    CACHE_TTL = 60  # 1 minute

    # Limited search depth for faster tests
    MAX_SEARCH_DEPTH = 2
    BFS_BATCH_SIZE = 10

    # Quick task timeouts for testing
    CELERY_TASK_SOFT_TIME_LIMIT = 10
    CELERY_TASK_TIME_LIMIT = 20

    # No rate limiting in tests
    API_RATE_LIMIT = "10000 per hour"

    # Disable external API calls in some tests
    MOCK_WIKIPEDIA_API = True
