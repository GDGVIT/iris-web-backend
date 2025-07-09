import os
from app import create_app

# Create the Flask application instance from the app factory
app = create_app()

if __name__ == "__main__":
    # This block runs the application.
    # The app.run() method is great for local development.
    # For a production environment, you would use a proper WSGI server like Gunicorn.
    # Example for production: gunicorn --bind 0.0.0.0:5000 run:app

    # Get the port from environment variables, defaulting to 5000
    port = int(9020)

    # Run the development server
    app.run(host="0.0.0.0", port=port, debug=True)
