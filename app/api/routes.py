from flask import (
    Blueprint,
    request,
    jsonify,
    send_from_directory,
    current_app,
    redirect,
    url_for,
)
from app.api.middleware import api_endpoint
from app.api.schemas import (
    SearchRequestSchema,
    ExploreRequestSchema,
    validate_request_data,
    serialize_response,
    ExploreResultSchema,
)
from app.core.factory import get_pathfinding_service, get_explore_service
from app.infrastructure.tasks import find_path_task
from app.utils.logging import get_logger

logger = get_logger(__name__)
main = Blueprint("main", __name__)


@main.route("/getPath", methods=["POST"])
@api_endpoint()
def get_path_route():
    """
    Initiate pathfinding between two Wikipedia pages.

    Returns a task ID for polling the result.
    """
    # Validate request data
    search_request = validate_request_data(SearchRequestSchema, request.get_json())

    logger.info(
        f"Path request: {search_request.start_page} -> {search_request.end_page}"
    )

    # Start background task
    task = find_path_task.delay(
        search_request.start_page, search_request.end_page, search_request.algorithm
    )

    response_data = {
        "status": "IN_PROGRESS",
        "task_id": task.id,
        "poll_url": f"/tasks/status/{task.id}",
        "start_page": search_request.start_page,
        "end_page": search_request.end_page,
    }

    return jsonify(response_data), 202


@main.route("/tasks/status/<task_id>", methods=["GET"])
@api_endpoint(require_json_content=False)
def get_task_status_route(task_id):
    """
    Get the status of a background task.

    Args:
        task_id: Celery task ID
    """
    task = find_path_task.AsyncResult(task_id)

    if task.state == "PENDING":
        response_data = {
            "status": "PENDING",
            "task_id": task_id,
            "message": "Task is waiting to be processed",
        }
    elif task.state == "PROGRESS":
        response_data = {
            "status": "IN_PROGRESS",
            "task_id": task_id,
            "progress": task.info,
        }
    elif task.state == "SUCCESS":
        result = task.result
        if isinstance(result, dict) and result.get("status") == "SUCCESS":
            response_data = {
                "status": "SUCCESS",
                "task_id": task_id,
                "result": {
                    "path": result.get("path", []),
                    "length": result.get("length", 0),
                    "search_time": result.get("search_time"),
                    "nodes_explored": result.get("nodes_explored"),
                    "search_stats": result.get("search_stats"),
                },
            }
        else:
            response_data = {"status": "SUCCESS", "task_id": task_id, "result": result}
    elif task.state == "FAILURE":
        response_data = {
            "status": "FAILURE",
            "task_id": task_id,
            "error": str(task.info),
        }
    else:
        response_data = {
            "status": task.state,
            "task_id": task_id,
            "info": str(task.info),
        }

    return jsonify(response_data)


@main.route("/explore", methods=["POST"])
@api_endpoint()
def explore_route():
    """
    Explore connections from a Wikipedia page for visualization.
    """
    # Validate request data
    explore_request = validate_request_data(ExploreRequestSchema, request.get_json())

    logger.info(
        f"Explore request: {explore_request.start_page} (max_links: {explore_request.max_links})"
    )

    # Get explore service and perform exploration
    explore_service = get_explore_service()
    result = explore_service.explore_page(explore_request)

    # Serialize response
    response_data = serialize_response(ExploreResultSchema, result)

    return jsonify(response_data), 200


@main.route("/health", methods=["GET"])
@api_endpoint(require_json_content=False, log_request=False)
def health_check():
    """
    Health check endpoint to verify system status.
    """
    try:
        from app.core.factory import ServiceFactory

        # Check Redis connection
        redis_status = "healthy"
        try:
            redis_client = ServiceFactory.get_redis_client()
            redis_client.ping()
        except Exception as e:
            redis_status = f"unhealthy: {str(e)}"

        # Check cache service
        cache_status = "healthy"
        try:
            cache_service = ServiceFactory.get_cache_service()
            cache_service.set("health_check", "ok", ttl=60)
            cache_value = cache_service.get("health_check")
            if cache_value != "ok":
                cache_status = "unhealthy: cache test failed"
        except Exception as e:
            cache_status = f"unhealthy: {str(e)}"

        # Check Wikipedia API (basic connectivity)
        wikipedia_status = "healthy"
        try:
            wikipedia_client = ServiceFactory.get_wikipedia_client()
            # Just check if we can create the client, don't make actual API call
        except Exception as e:
            wikipedia_status = f"unhealthy: {str(e)}"

        # Determine overall status
        if all(
            status == "healthy"
            for status in [redis_status, cache_status, wikipedia_status]
        ):
            overall_status = "healthy"
            status_code = 200
        else:
            overall_status = "degraded"
            status_code = 503

        response_data = {
            "status": overall_status,
            "redis_status": redis_status,
            "cache_status": cache_status,
            "wikipedia_api_status": wikipedia_status,
            "timestamp": "2025-01-31T00:00:00Z",  # Would use actual timestamp
        }

        return jsonify(response_data), status_code

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        error_response = {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": "2025-01-31T00:00:00Z",
        }
        return jsonify(error_response), 503


@main.route("/cache/clear", methods=["POST"])
@api_endpoint()
def clear_cache():
    """
    Clear cache entries (admin endpoint).
    """
    data = request.get_json()
    pattern = data.get("pattern", "wiki_links:*")

    try:
        from app.core.factory import get_cache_management_service

        cache_service = get_cache_management_service()
        cleared_count = cache_service.clear_cache_pattern(pattern)

        response_data = {
            "success": True,
            "message": f"Cleared {cleared_count} cache entries",
            "pattern": pattern,
        }
        return jsonify(response_data), 200

    except Exception as e:
        logger.error(f"Cache clear failed: {e}")
        raise


@main.route("/")
@api_endpoint(require_json_content=False, log_request=False)
def index():
    """
    Serve the path visualization UI (main landing page).
    """
    try:
        import os

        static_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static"
        )
        return send_from_directory(static_dir, "index.html")
    except Exception as e:
        logger.error(f"Failed to serve UI: {e}")
        return jsonify({"error": "UI not available"}), 404


@main.route("/ui")
def ui_redirect():
    """
    Redirect /ui to main page for backward compatibility.
    """
    return redirect(url_for("main.index"))


@main.route("/static/<path:filename>")
@api_endpoint(require_json_content=False, log_request=False)
def static_files(filename):
    """
    Serve static files for the UI.
    """
    try:
        import os

        static_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static"
        )
        return send_from_directory(static_dir, filename)
    except Exception as e:
        logger.error(f"Failed to serve static file {filename}: {e}")
        return jsonify({"error": "File not found"}), 404


@main.route("/api", methods=["GET"])
@api_endpoint(require_json_content=False, log_request=False)
def api_info():
    """
    API information endpoint.
    """
    response_data = {
        "name": "Iris Wikipedia Pathfinder API",
        "version": "2.0.0",
        "description": "Find shortest paths between Wikipedia pages",
        "endpoints": {
            "POST /getPath": "Start pathfinding between two pages",
            "GET /tasks/status/<task_id>": "Check task status",
            "POST /explore": "Explore page connections",
            "GET /health": "Health check",
            "GET /ui": "Path visualization UI",
            "GET /api": "API information",
        },
        "documentation": "./API_DOCUMENTATION.md",
        "ui_url": "/ui",
    }
    return jsonify(response_data)


# Catch-all route for non-API paths
@main.route("/<path:path>")
def catch_all(path):
    """
    Redirect all non-API paths to main UI.
    Only redirect if it's not an API endpoint or static file.
    """
    # List of API endpoints that should return JSON errors instead of redirecting
    api_paths = ["getPath", "tasks", "explore", "health", "cache", "api"]

    # Check if this is an API call
    if any(path.startswith(api_path) for api_path in api_paths):
        response_data = {
            "error": True,
            "message": "Endpoint not found",
            "code": "NOT_FOUND",
        }
        return jsonify(response_data), 404

    # For all other paths, redirect to main UI
    return redirect(url_for("main.index"))


# Error handlers for the blueprint
@main.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    # This will only catch 404s that aren't handled by catch_all
    response_data = {
        "error": True,
        "message": "Endpoint not found",
        "code": "NOT_FOUND",
    }
    return jsonify(response_data), 404


@main.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors."""
    response_data = {
        "error": True,
        "message": "Method not allowed",
        "code": "METHOD_NOT_ALLOWED",
    }
    return jsonify(response_data), 405


@main.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}")
    response_data = {
        "error": True,
        "message": "Internal server error",
        "code": "INTERNAL_ERROR",
    }
    return jsonify(response_data), 500
