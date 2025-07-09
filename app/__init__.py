import logging
from flask import Flask
from celery import Celery
from config import Config

# Initialize Celery
celery = Celery(__name__, broker=Config.REDIS_URL, backend=Config.REDIS_URL)


def create_app(config_class=Config):
    """
    Creates and configures the Flask application instance.
    This is the application factory.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]",
    )

    celery.conf.task_acks_late = True
    celery.conf.worker_prefetch_multiplier = 1

    # Update Celery configuration with Flask app config
    celery.conf.update(app.config)

    # Register the blueprints
    from app.routes import main as main_blueprint

    app.register_blueprint(main_blueprint, url_prefix="/")

    return app
