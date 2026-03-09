#!/bin/sh
set -e

if [ "$SERVICE_TYPE" = "worker" ]; then
    echo "Starting Celery worker..."
    exec celery -A celery_worker.celery worker --loglevel=info --queues=celery,pathfinding,health,maintenance --max-tasks-per-child=3 --concurrency=2
else
    echo "Starting gunicorn web server on port ${PORT:-8080}..."
    exec gunicorn --bind "0.0.0.0:${PORT:-8080}" --workers 2 --timeout 120 run:app
fi
