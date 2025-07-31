from config.base import BaseConfig


class ProductionConfig(BaseConfig):
    """Production-specific configuration."""

    DEBUG = False
    TESTING = False

    # Production logging
    LOG_LEVEL = "INFO"

    # Production cache settings
    CACHE_TTL = 86400  # 24 hours

    # Production pathfinding limits
    MAX_SEARCH_DEPTH = 6
    BFS_BATCH_SIZE = 50

    # Production task timeouts
    CELERY_TASK_SOFT_TIME_LIMIT = 300  # 5 minutes
    CELERY_TASK_TIME_LIMIT = 600  # 10 minutes

    # Production API settings
    API_RATE_LIMIT = "100 per hour"

    # Security settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
