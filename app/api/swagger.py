"""OpenAPI/Swagger specification for the Iris API."""

SWAGGER_TEMPLATE = {
    "swagger": "2.0",
    "info": {
        "title": "Iris Wikipedia Pathfinder API",
        "description": "Find shortest paths between Wikipedia pages using Redis-based BFS.",
        "version": "2.0.0",
        "contact": {"name": "Iris"},
        "license": {"name": "MIT"},
    },
    "basePath": "/",
    "schemes": ["https", "http"],
    "consumes": ["application/json"],
    "produces": ["application/json"],
    "tags": [
        {"name": "Pathfinding", "description": "Find paths between Wikipedia pages"},
        {"name": "Exploration", "description": "Explore page connections"},
        {"name": "System", "description": "Health and administration"},
    ],
    "paths": {
        "/getPath": {
            "post": {
                "summary": "Start pathfinding",
                "description": "Queue a background task to find the shortest path between two Wikipedia pages. Returns a task ID to poll for results.",
                "tags": ["Pathfinding"],
                "parameters": [
                    {
                        "in": "body",
                        "name": "body",
                        "required": True,
                        "schema": {
                            "type": "object",
                            "required": ["start_page", "end_page"],
                            "properties": {
                                "start_page": {
                                    "type": "string",
                                    "example": "Python (programming language)",
                                    "description": "Wikipedia page title to start from",
                                },
                                "end_page": {
                                    "type": "string",
                                    "example": "Monty Python",
                                    "description": "Wikipedia page title to reach",
                                },
                                "algorithm": {
                                    "type": "string",
                                    "enum": ["bfs", "bidirectional"],
                                    "default": "bfs",
                                    "description": "Pathfinding algorithm",
                                },
                            },
                        },
                    }
                ],
                "responses": {
                    "202": {
                        "description": "Task accepted",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "status": {"type": "string", "example": "IN_PROGRESS"},
                                "task_id": {"type": "string"},
                                "poll_url": {"type": "string"},
                                "start_page": {"type": "string"},
                                "end_page": {"type": "string"},
                            },
                        },
                    },
                    "400": {"description": "Validation error"},
                },
            }
        },
        "/tasks/status/{task_id}": {
            "get": {
                "summary": "Get task status",
                "description": "Poll for task result and real-time progress updates.",
                "tags": ["Pathfinding"],
                "parameters": [
                    {
                        "name": "task_id",
                        "in": "path",
                        "required": True,
                        "type": "string",
                        "description": "Celery task ID from /getPath response",
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Task status",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "status": {
                                    "type": "string",
                                    "enum": [
                                        "PENDING",
                                        "IN_PROGRESS",
                                        "SUCCESS",
                                        "FAILURE",
                                    ],
                                },
                                "task_id": {"type": "string"},
                                "result": {
                                    "type": "object",
                                    "properties": {
                                        "path": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        },
                                        "length": {"type": "integer"},
                                        "search_time": {"type": "number"},
                                        "nodes_explored": {"type": "integer"},
                                    },
                                },
                                "progress": {"type": "object"},
                            },
                        },
                    }
                },
            }
        },
        "/explore": {
            "post": {
                "summary": "Explore page connections",
                "description": "Fetch outgoing links from a Wikipedia page for graph visualization.",
                "tags": ["Exploration"],
                "parameters": [
                    {
                        "in": "body",
                        "name": "body",
                        "required": True,
                        "schema": {
                            "type": "object",
                            "required": ["start_page"],
                            "properties": {
                                "start_page": {
                                    "type": "string",
                                    "example": "Python (programming language)",
                                },
                                "max_links": {
                                    "type": "integer",
                                    "default": 10,
                                    "description": "Maximum number of links to return",
                                },
                            },
                        },
                    }
                ],
                "responses": {
                    "200": {"description": "Page connections"},
                    "400": {"description": "Validation error"},
                    "404": {"description": "Page not found"},
                },
            }
        },
        "/health": {
            "get": {
                "summary": "Health check",
                "description": "Verify Redis, cache, and Wikipedia API connectivity.",
                "tags": ["System"],
                "responses": {
                    "200": {"description": "All systems healthy"},
                    "503": {"description": "One or more systems degraded"},
                },
            }
        },
        "/cache/clear": {
            "post": {
                "summary": "Clear cache",
                "description": "Clear Redis cache entries matching a key pattern.",
                "tags": ["System"],
                "parameters": [
                    {
                        "in": "body",
                        "name": "body",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "pattern": {
                                    "type": "string",
                                    "default": "wiki_links:*",
                                    "description": "Redis key pattern to clear",
                                }
                            },
                        },
                    }
                ],
                "responses": {
                    "200": {"description": "Cache cleared successfully"},
                },
            }
        },
        "/api": {
            "get": {
                "summary": "API info",
                "description": "Returns API metadata and endpoint list.",
                "tags": ["System"],
                "responses": {
                    "200": {"description": "API information"},
                },
            }
        },
    },
}

SWAGGER_CONFIG = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/api/docs",
}
