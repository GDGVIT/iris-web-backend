import logging
import os
from logging.handlers import RotatingFileHandler


def configure_logging(app):
    """Configure logging for the Flask application."""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_format = os.environ.get(
        "LOG_FORMAT",
        "%(asctime)s %(levelname)s [%(name)s] %(message)s [in %(pathname)s:%(lineno)d]",
    )

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level), format=log_format, handlers=[]
    )

    # Create formatter
    formatter = logging.Formatter(log_format)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, log_level))

    # Add handlers to app logger
    app.logger.addHandler(console_handler)
    app.logger.setLevel(getattr(logging, log_level))

    # File handler for production
    if not app.debug and not app.testing:
        log_dir = os.environ.get("LOG_DIR", "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        file_handler = RotatingFileHandler(
            os.path.join(log_dir, "iris.log"),
            maxBytes=1024 * 1024 * 10,  # 10MB
            backupCount=10,
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)

    app.logger.info("Logging configured successfully")


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)
