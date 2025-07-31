from functools import wraps
from flask import request, jsonify, current_app
from marshmallow import ValidationError
from app.utils.exceptions import (
    IrisBaseException,
    PathNotFoundError,
    InvalidPageError,
    WikipediaPageNotFoundError,
    CacheConnectionError,
    TaskError,
)
from app.utils.logging import get_logger
import time

logger = get_logger(__name__)


def handle_validation_errors(f):
    """Decorator to handle validation errors in API endpoints."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValidationError as e:
            error_response = {
                "error": True,
                "message": "Invalid request data",
                "code": "VALIDATION_ERROR",
                "details": e.messages,
            }
            return jsonify(error_response), 400

    return decorated_function


def handle_application_errors(f):
    """Decorator to handle application-specific errors."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except PathNotFoundError as e:
            error_response = {
                "error": True,
                "message": str(e),
                "code": "PATH_NOT_FOUND",
            }
            return jsonify(error_response), 404
        except InvalidPageError as e:
            error_response = {"error": True, "message": str(e), "code": "INVALID_PAGE"}
            return jsonify(error_response), 400
        except WikipediaPageNotFoundError as e:
            error_response = {
                "error": True,
                "message": str(e),
                "code": "WIKIPEDIA_PAGE_NOT_FOUND",
            }
            return jsonify(error_response), 404
        except CacheConnectionError as e:
            error_response = {
                "error": True,
                "message": "Cache service unavailable",
                "code": "CACHE_ERROR",
            }
            logger.error(f"Cache error: {e}")
            return jsonify(error_response), 503
        except TaskError as e:
            error_response = {"error": True, "message": str(e), "code": "TASK_ERROR"}
            return jsonify(error_response), 500
        except IrisBaseException as e:
            error_response = {
                "error": True,
                "message": str(e),
                "code": "APPLICATION_ERROR",
            }
            return jsonify(error_response), 500
        except Exception as e:
            error_response = {
                "error": True,
                "message": "Internal server error",
                "code": "INTERNAL_ERROR",
            }
            logger.error(f"Unexpected error: {e}", exc_info=True)
            return jsonify(error_response), 500

    return decorated_function


def log_requests(f):
    """Decorator to log API requests and responses."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()

        # Log request
        logger.info(
            f"API Request: {request.method} {request.path} from {request.remote_addr}"
        )
        if request.is_json and request.get_json():
            logger.debug(f"Request data: {request.get_json()}")

        try:
            response = f(*args, **kwargs)
            duration = time.time() - start_time

            # Log response
            status_code = response[1] if isinstance(response, tuple) else 200
            logger.info(
                f"API Response: {request.method} {request.path} - {status_code} ({duration:.3f}s)"
            )

            return response
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"API Error: {request.method} {request.path} - Error ({duration:.3f}s): {e}"
            )
            raise

    return decorated_function


def require_json(f):
    """Decorator to ensure request has JSON content type."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json:
            error_response = {
                "error": True,
                "message": "Request must have Content-Type: application/json",
                "code": "INVALID_CONTENT_TYPE",
            }
            return jsonify(error_response), 400
        return f(*args, **kwargs)

    return decorated_function


def rate_limit(max_requests_per_hour=100):
    """
    Simple rate limiting decorator (in production, use Redis-based rate limiting).

    Args:
        max_requests_per_hour: Maximum requests per hour per IP
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # In a real implementation, you would use Redis to track requests per IP
            # For now, just log the request and continue
            client_ip = request.remote_addr
            logger.debug(
                f"Rate limit check for {client_ip} (limit: {max_requests_per_hour}/hour)"
            )
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def cors_headers(f):
    """Add CORS headers to response."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = f(*args, **kwargs)

        # Handle tuple responses (data, status_code)
        if isinstance(response, tuple):
            data, status_code = response
            # Don't re-jsonify if data is already a Response object
            if hasattr(data, "headers"):
                # data is already a Response object
                response = data
                response.status_code = status_code
            else:
                # data is raw data, needs to be jsonified
                response = jsonify(data)
                response.status_code = status_code
        elif not hasattr(response, "headers"):
            # Response is raw data, needs to be jsonified
            response = jsonify(response)

        # Add CORS headers
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"

        return response

    return decorated_function


def validate_request_size(max_size_mb=1):
    """Validate request size to prevent large payloads."""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if (
                request.content_length
                and request.content_length > max_size_mb * 1024 * 1024
            ):
                error_response = {
                    "error": True,
                    "message": f"Request too large. Maximum size: {max_size_mb}MB",
                    "code": "REQUEST_TOO_LARGE",
                }
                return jsonify(error_response), 413
            return f(*args, **kwargs)

        return decorated_function

    return decorator


# Combined decorator for common API middleware
def api_endpoint(
    require_json_content=True,
    log_request=True,
    handle_errors=True,
    add_cors=True,
    max_requests_per_hour=100,
    max_size_mb=1,
):
    """
    Combined decorator that applies common API middleware.

    Usage:
        @api_endpoint()
        def my_endpoint():
            pass
    """

    def decorator(f):
        # Apply decorators in reverse order (they wrap inside-out)
        if handle_errors:
            f = handle_application_errors(f)
            f = handle_validation_errors(f)

        if add_cors:
            f = cors_headers(f)

        if max_size_mb:
            f = validate_request_size(max_size_mb)(f)

        if max_requests_per_hour:
            f = rate_limit(max_requests_per_hour)(f)

        if require_json_content:
            f = require_json(f)

        if log_request:
            f = log_requests(f)

        return f

    return decorator
