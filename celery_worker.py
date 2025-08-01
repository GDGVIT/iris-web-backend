# Import the Flask app and Celery instances from the app factory
from app import create_app, celery

# Create the Flask app instance
app = create_app()

# Push an application context to make it available to the Celery tasks.
# This ensures that tasks can access app configurations and extensions.
app.app_context().push()
