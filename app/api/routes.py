import os

from flask import Blueprint, jsonify, redirect, request, send_from_directory, url_for

from app.api.middleware import api_endpoint
from app.api.schemas import (
    ExploreRequestSchema,
    ExploreResultSchema,
    SearchRequestSchema,
    serialize_response,
    validate_request_data,
)
from app.core.factory import (
    ServiceFactory,
    get_cache_management_service,
    get_explore_service,
)
from app.infrastructure.tasks import find_path_task
from app.utils.logging import get_logger

logger = get_logger(__name__)
main = Blueprint("main", __name__)

_STATIC_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "static"
)


@main.route("/getPath", methods=["POST"])
@api_endpoint()
def get_path_route():
    """Queue a background task to find a path between two Wikipedia pages.
    ---
    tags:
      - Pathfinding
    summary: Start pathfinding
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - start_page
            - end_page
          properties:
            start_page:
              type: string
              example: "Python (programming language)"
              description: Wikipedia page title to start from
            end_page:
              type: string
              example: "Monty Python"
              description: Wikipedia page title to reach
            algorithm:
              type: string
              enum: [bfs, bidirectional]
              default: bidirectional
              description: >
                Pathfinding algorithm. "bidirectional" (default) searches from
                both the start and end pages simultaneously using Wikipedia
                backlinks for the reverse frontier, typically finding shorter
                paths faster. "bfs" uses standard forward-only BFS.
    responses:
      202:
        description: Task accepted, poll poll_url for results
        schema:
          type: object
          properties:
            status:
              type: string
              example: IN_PROGRESS
            task_id:
              type: string
            poll_url:
              type: string
            start_page:
              type: string
            end_page:
              type: string
      400:
        description: Validation error
    """
    search_request = validate_request_data(SearchRequestSchema, request.get_json())

    logger.info(
        f"Path request: {search_request.start_page} -> {search_request.end_page}"
    )

    task = find_path_task.delay(  # type: ignore[attr-defined]
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
    """Poll for task result and real-time progress updates.
    ---
    tags:
      - Pathfinding
    summary: Get task status
    parameters:
      - name: task_id
        in: path
        required: true
        type: string
        description: Celery task ID returned by POST /getPath
    responses:
      200:
        description: Task status
        schema:
          type: object
          properties:
            status:
              type: string
              enum: [PENDING, IN_PROGRESS, SUCCESS, FAILURE]
            task_id:
              type: string
            result:
              type: object
              properties:
                path:
                  type: array
                  items:
                    type: string
                length:
                  type: integer
                search_time:
                  type: number
                nodes_explored:
                  type: integer
            progress:
              type: object
    """
    task = find_path_task.AsyncResult(task_id)  # type: ignore[attr-defined]

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
    """Fetch outgoing links from a Wikipedia page for graph visualization.
    ---
    tags:
      - Exploration
    summary: Explore page connections
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - start_page
          properties:
            start_page:
              type: string
              example: "Python (programming language)"
            max_links:
              type: integer
              default: 10
              description: Maximum number of links to return
    responses:
      200:
        description: Page connections for visualization
      400:
        description: Validation error
      404:
        description: Page not found
    """
    explore_request = validate_request_data(ExploreRequestSchema, request.get_json())

    logger.info(
        f"Explore request: {explore_request.start_page} (max_links: {explore_request.max_links})"
    )

    explore_service = get_explore_service()
    result = explore_service.explore_page(explore_request)

    response_data = serialize_response(ExploreResultSchema, result)

    return jsonify(response_data), 200


@main.route("/health", methods=["GET"])
@api_endpoint(require_json_content=False, log_request=False)
def health_check():
    """Verify Redis, cache, and Wikipedia API connectivity.
    ---
    tags:
      - System
    summary: Health check
    responses:
      200:
        description: All systems healthy
      503:
        description: One or more systems degraded
    """
    try:
        redis_status = "healthy"
        try:
            redis_client = ServiceFactory.get_redis_client()
            redis_client.ping()
        except Exception as e:
            redis_status = f"unhealthy: {e}"

        cache_status = "healthy"
        try:
            cache_service = ServiceFactory.get_cache_service()
            cache_service.set("health_check", "ok", ttl=60)
            cache_value = cache_service.get("health_check")
            if cache_value != "ok":
                cache_status = "unhealthy: cache test failed"
        except Exception as e:
            cache_status = f"unhealthy: {e}"

        wikipedia_status = "healthy"
        try:
            ServiceFactory.get_wikipedia_client()
        except Exception as e:
            wikipedia_status = f"unhealthy: {e}"

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
        }

        return jsonify(response_data), status_code

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 503


@main.route("/cache/clear", methods=["POST"])
@api_endpoint()
def clear_cache():
    """Clear Redis cache entries matching a key pattern.
    ---
    tags:
      - System
    summary: Clear cache
    parameters:
      - in: body
        name: body
        schema:
          type: object
          properties:
            pattern:
              type: string
              default: "wiki_links:*"
              description: Redis key pattern to clear
    responses:
      200:
        description: Cache cleared successfully
    """
    data = request.get_json()
    pattern = data.get("pattern", "wiki_links:*")

    try:
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
    """Serve the path visualization UI (main landing page)."""
    try:
        return send_from_directory(_STATIC_DIR, "index.html")
    except Exception as e:
        logger.error(f"Failed to serve UI: {e}")
        return jsonify({"error": "UI not available"}), 404


@main.route("/ui")
def ui_redirect():
    """Redirect /ui to main page for backward compatibility."""
    return redirect(url_for("main.index"))


@main.route("/static/<path:filename>")
@api_endpoint(require_json_content=False, log_request=False)
def static_files(filename):
    """Serve static files for the UI."""
    try:
        return send_from_directory(_STATIC_DIR, filename)
    except Exception as e:
        logger.error(f"Failed to serve static file {filename}: {e}")
        return jsonify({"error": "File not found"}), 404


@main.route("/api", methods=["GET"])
@api_endpoint(require_json_content=False, log_request=False)
def api_info():
    """Returns API metadata and available endpoints.
    ---
    tags:
      - System
    summary: API info
    responses:
      200:
        description: API information and endpoint list
    """
    response_data = {
        "name": "Iris Wikipedia Pathfinder API",
        "version": "2.0.0",
        "description": "Find paths between Wikipedia pages",
        "endpoints": {
            "POST /getPath": "Start pathfinding between two pages",
            "GET /tasks/status/<task_id>": "Check task status",
            "POST /explore": "Explore page connections",
            "GET /health": "Health check",
            "GET /": "Path visualization UI",
            "GET /api": "API information",
            "GET /api/docs": "Swagger UI",
        },
        "swagger_ui": "/api/docs",
    }
    return jsonify(response_data)


@main.route("/<path:path>")
def catch_all(path):
    """Redirect all non-API paths to main UI."""
    api_paths = ["getPath", "tasks", "explore", "health", "cache", "api"]

    if any(path.startswith(api_path) for api_path in api_paths):
        response_data = {
            "error": True,
            "message": "Endpoint not found",
            "code": "NOT_FOUND",
        }
        return jsonify(response_data), 404

    return redirect(url_for("main.index"))


@main.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify(
        {"error": True, "message": "Endpoint not found", "code": "NOT_FOUND"}
    ), 404


@main.errorhandler(405)
def method_not_allowed(error):
    """Handle 405 errors."""
    return (
        jsonify(
            {
                "error": True,
                "message": "Method not allowed",
                "code": "METHOD_NOT_ALLOWED",
            }
        ),
        405,
    )


@main.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}")
    return (
        jsonify(
            {
                "error": True,
                "message": "Internal server error",
                "code": "INTERNAL_ERROR",
            }
        ),
        500,
    )
