import os
from dotenv import load_dotenv
from app.utils.exceptions import ConfigurationError

# Load environment variables from .env file
load_dotenv()


class BaseConfig:
    """Base configuration with common settings."""

    # Flask settings
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        raise ConfigurationError("SECRET_KEY environment variable is required")

    # Redis and Celery settings
    REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

    # Wikipedia API settings
    WIKIPEDIA_API_TIMEOUT = int(os.environ.get("WIKIPEDIA_API_TIMEOUT", "15"))
    WIKIPEDIA_BATCH_SIZE = int(os.environ.get("WIKIPEDIA_BATCH_SIZE", "50"))
    WIKIPEDIA_MAX_WORKERS = int(os.environ.get("WIKIPEDIA_MAX_WORKERS", "10"))

    # Cache settings
    CACHE_TTL = int(os.environ.get("CACHE_TTL", "86400"))  # 24 hours
    CACHE_PREFIX = os.environ.get("CACHE_PREFIX", "iris")

    # Pathfinding settings
    MAX_SEARCH_DEPTH = int(os.environ.get("MAX_SEARCH_DEPTH", "6"))
    BFS_BATCH_SIZE = int(os.environ.get("BFS_BATCH_SIZE", "50"))

    # Celery settings
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_TASK_ACKS_LATE = True
    CELERY_WORKER_PREFETCH_MULTIPLIER = 1
    CELERY_TASK_SOFT_TIME_LIMIT = int(
        os.environ.get("CELERY_TASK_SOFT_TIME_LIMIT", "300")
    )  # 5 minutes
    CELERY_TASK_TIME_LIMIT = int(
        os.environ.get("CELERY_TASK_TIME_LIMIT", "600")
    )  # 10 minutes

    # API settings
    API_RATE_LIMIT = os.environ.get("API_RATE_LIMIT", "100 per hour")
    API_TIMEOUT = int(os.environ.get("API_TIMEOUT", "30"))

    # Logging settings
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
    LOG_FORMAT = os.environ.get(
        "LOG_FORMAT",
        "%(asctime)s %(levelname)s [%(name)s] %(message)s [in %(pathname)s:%(lineno)d]",
    )
    LOG_DIR = os.environ.get("LOG_DIR", "logs")

    # Health check settings
    HEALTH_CHECK_ENABLED = (
        os.environ.get("HEALTH_CHECK_ENABLED", "true").lower() == "true"
    )

    @classmethod
    def validate_config(cls):
        """Validate configuration settings."""
        errors = []

        # Check required settings
        if not cls.SECRET_KEY:
            errors.append("SECRET_KEY is required")

        # Validate numeric settings
        try:
            if cls.WIKIPEDIA_API_TIMEOUT <= 0:
                errors.append("WIKIPEDIA_API_TIMEOUT must be positive")
            if cls.WIKIPEDIA_BATCH_SIZE <= 0:
                errors.append("WIKIPEDIA_BATCH_SIZE must be positive")
            if cls.MAX_SEARCH_DEPTH <= 0:
                errors.append("MAX_SEARCH_DEPTH must be positive")
        except (ValueError, TypeError):
            errors.append("Invalid numeric configuration values")

        # Validate Redis URL format
        if not cls.REDIS_URL.startswith(("redis://", "rediss://")):
            errors.append("REDIS_URL must be a valid Redis URL")

        if errors:
            raise ConfigurationError(
                f"Configuration validation failed: {', '.join(errors)}"
            )

        return True
