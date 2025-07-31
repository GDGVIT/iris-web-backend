from config.base import BaseConfig


class DevelopmentConfig(BaseConfig):
    """Development-specific configuration."""

    DEBUG = True
    TESTING = False

    # More verbose logging in development
    LOG_LEVEL = "DEBUG"

    # Shorter cache TTL for development
    CACHE_TTL = 3600  # 1 hour

    # Lower limits for development
    MAX_SEARCH_DEPTH = 4
    BFS_BATCH_SIZE = 20

    # More aggressive task timeouts for development
    CELERY_TASK_SOFT_TIME_LIMIT = 60  # 1 minute
    CELERY_TASK_TIME_LIMIT = 120  # 2 minutes

    # Development-specific API settings
    API_RATE_LIMIT = "1000 per hour"  # More lenient for development
