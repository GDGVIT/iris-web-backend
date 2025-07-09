web: gunicorn --bind 0.0.0.0:9020 run:app
worker: celery -A celery_worker.celery worker --loglevel=info