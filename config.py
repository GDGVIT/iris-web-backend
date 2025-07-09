import os
from dotenv import load_dotenv

# Load environment variables from the .env file
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))


class Config:
    """
    Sets configuration variables for the Flask application.
    Loads values from the environment .env file.
    """

    # Flask settings
    SECRET_KEY = os.environ.get("SECRET_KEY") or "you-will-never-guess"

    # Google reCAPTCHA settings
    RECAPTCHA_SECRET_KEY = os.environ.get("RECAPTCHA_SECRET_KEY")

    # Redis and Celery settings
    REDIS_URL = os.environ.get("REDIS_URL") or "redis://localhost:6379/0"
