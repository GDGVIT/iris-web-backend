import os
import uuid

from celery import Celery
from celery.signals import after_setup_logger, after_setup_task_logger
from flasgger import Swagger
from flask import Flask, g, jsonify
from marshmallow import ValidationError

from app.api.swagger import SWAGGER_CONFIG, SWAGGER_TEMPLATE
from app.utils.constants import ERROR_INTERNAL_ERROR
from app.utils.exceptions import IrisBaseException
from app.utils.logging import JSONFormatter, RequestContextFilter, configure_logging
from config.development import DevelopmentConfig
from config.production import ProductionConfig
from config.testing import TestingConfig

# Initialize Celery
celery = Celery(__name__)


def create_app(config_class=None):
    """
    Creates and configures the Flask application instance.
    This is the application factory.
    """
    static_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    app = Flask(__name__, static_folder=static_folder)

    # Determine configuration class
    if config_class is None:
        env = os.environ.get("FLASK_ENV", "development")
        if env == "production":
            config_class = ProductionConfig
        elif env == "testing":
            config_class = TestingConfig
        else:
            config_class = DevelopmentConfig

    app.config.from_object(config_class)

    # Validate configuration
    config_class.validate_config()

    # Configure logging
    configure_logging(app)

    # Configure Celery
    configure_celery(app)

    # Initialize Swagger UI
    Swagger(app, template=SWAGGER_TEMPLATE, config=SWAGGER_CONFIG)

    # Attach a unique request_id to every incoming request
    @app.before_request
    def set_request_id():
        g.request_id = str(uuid.uuid4())

    # Register blueprints
    register_blueprints(app)

    # Register error handlers
    register_error_handlers(app)

    app.logger.info("app_created", extra={"config": config_class.__name__})
    return app


def configure_celery(app):
    """Configure Celery with Flask app."""
    celery.conf.update(
        broker_url=app.config["CELERY_BROKER_URL"],
        result_backend=app.config["CELERY_RESULT_BACKEND"],
        task_acks_late=app.config["CELERY_TASK_ACKS_LATE"],
        worker_prefetch_multiplier=app.config["CELERY_WORKER_PREFETCH_MULTIPLIER"],
        task_soft_time_limit=app.config["CELERY_TASK_SOFT_TIME_LIMIT"],
        task_time_limit=app.config["CELERY_TASK_TIME_LIMIT"],
        # Prevent Celery from replacing our root-logger handlers on worker startup
        worker_hijack_root_logger=False,
    )

    # After Celery sets up any loggers of its own, replace their formatters with ours
    def _apply_json_formatter(logger, **kwargs):
        for handler in logger.handlers:
            handler.setFormatter(JSONFormatter())
            handler.addFilter(RequestContextFilter())

    after_setup_logger.connect(_apply_json_formatter)
    after_setup_task_logger.connect(_apply_json_formatter)

    # Configure task routes and periodic tasks
    from app.infrastructure.tasks import configure_periodic_tasks, configure_task_routes

    configure_task_routes(celery)
    configure_periodic_tasks(celery)

    class ContextTask(celery.Task):
        """Make celery tasks work with Flask app context."""

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    app.logger.info("Celery configured successfully")


def register_blueprints(app):
    """Register Flask blueprints."""
    from app.api.routes import main as main_blueprint

    app.register_blueprint(main_blueprint, url_prefix="/")
    app.logger.info("Blueprints registered successfully")


def register_error_handlers(app):
    """Register global error handlers."""

    @app.errorhandler(IrisBaseException)
    def handle_iris_exception(e):
        app.logger.error("iris_exception", extra={"error": str(e)})
        response = {"error": True, "message": str(e), "code": e.__class__.__name__}
        return jsonify(response), 500

    @app.errorhandler(ValidationError)
    def handle_validation_error(e):
        app.logger.warning("validation_error", extra={"error": str(e)})
        response = {
            "error": True,
            "message": "Validation failed",
            "code": "VALIDATION_ERROR",
            "details": e.messages,
        }
        return jsonify(response), 400

    @app.errorhandler(404)
    def handle_not_found(e):
        response = {"error": True, "message": "Resource not found", "code": "NOT_FOUND"}
        return jsonify(response), 404

    @app.errorhandler(405)
    def handle_method_not_allowed(e):
        response = {
            "error": True,
            "message": "Method not allowed",
            "code": "METHOD_NOT_ALLOWED",
        }
        return jsonify(response), 405

    @app.errorhandler(500)
    def handle_internal_error(e):
        app.logger.error("internal_server_error", extra={"error": str(e)})
        response = {
            "error": True,
            "message": "Internal server error",
            "code": ERROR_INTERNAL_ERROR,
        }
        return jsonify(response), 500

    app.logger.info("Error handlers registered successfully")
