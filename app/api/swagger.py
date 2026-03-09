"""Swagger/Flasgger configuration for the Iris API.

Top-level metadata only — paths are auto-collected from route docstrings.
"""

SWAGGER_TEMPLATE = {
    "swagger": "2.0",
    "info": {
        "title": "Iris Wikipedia Pathfinder API",
        "description": "Find paths between Wikipedia pages using Redis-based BFS.",
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
