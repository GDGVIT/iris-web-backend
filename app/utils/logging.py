import json
import logging
import os
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler

# Standard LogRecord attributes — excluded from the "extra" catch-all
_RECORD_ATTRS: frozenset[str] = frozenset(
    {
        # Standard LogRecord attributes (https://docs.python.org/3/library/logging.html#logrecord-attributes)
        "args",
        "asctime",  # set by Formatter.format() when %(asctime)s is used
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
        # injected by RequestContextFilter
        "request_id",
        "http_method",
        "http_path",
        "remote_addr",
    }
)


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()

        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
            "request_id": getattr(record, "request_id", ""),
            "http_method": getattr(record, "http_method", ""),
            "http_path": getattr(record, "http_path", ""),
            "remote_addr": getattr(record, "remote_addr", ""),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Append any caller-supplied extra fields (e.g. task_id, duration_ms)
        for key, val in record.__dict__.items():
            if key not in _RECORD_ATTRS and not key.startswith("_"):
                payload[key] = val

        return json.dumps(payload, default=str)


class RequestContextFilter(logging.Filter):
    """Injects Flask request-context fields into every log record.

    Safe to use outside a request context (Celery tasks, startup) — fields
    are set to empty strings when no request is active.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from flask import g, has_request_context
            from flask import request as flask_request

            if has_request_context():
                record.request_id = getattr(g, "request_id", "")
                record.http_method = flask_request.method
                record.http_path = flask_request.path
                record.remote_addr = flask_request.remote_addr or ""
                return True
        except Exception:
            pass

        record.request_id = ""
        record.http_method = ""
        record.http_path = ""
        record.remote_addr = ""
        return True


def _build_handler(handler: logging.Handler, level: int) -> logging.Handler:
    handler.setFormatter(JSONFormatter())
    handler.addFilter(RequestContextFilter())
    handler.setLevel(level)
    return handler


def configure_logging(app) -> None:
    """Configure JSON structured logging for the Flask application."""
    log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    console = _build_handler(logging.StreamHandler(), log_level)

    # Apply to the root logger so Celery, urllib3, etc. all emit JSON
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(console)
    root.setLevel(log_level)

    # Flask may attach its own default handler in debug mode; remove it so logs
    # don't double-print in plain text alongside our JSON handler.
    app.logger.handlers.clear()
    app.logger.setLevel(log_level)

    if not app.debug and not app.testing:
        log_dir = os.environ.get("LOG_DIR", "logs")
        os.makedirs(log_dir, exist_ok=True)
        file_handler = _build_handler(
            RotatingFileHandler(
                os.path.join(log_dir, "iris.log"),
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=10,
            ),
            logging.INFO,
        )
        root.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)

    app.logger.info("Logging configured", extra={"log_level": log_level_name})


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance. Call sites are unchanged from stdlib logging."""
    return logging.getLogger(name)
