#!/bin/bash
#
# start.sh — Manual production-like startup (single host, both services)
#
# Starts a Celery worker and Gunicorn (or Flask dev server) in the same
# process group. Useful for running both services on a single machine
# without Docker.
#
# For containerised deployments (Railway, Docker) use entrypoint.sh instead,
# which launches only the service specified by SERVICE_TYPE.
#
# Usage:
#   FLASK_ENV=production SECRET_KEY=... REDIS_URL=... ./start.sh
#
# Server runs at http://localhost:9020

set -e

echo "Starting Iris..."

if [ -z "$SECRET_KEY" ]; then
    echo "WARNING: SECRET_KEY not set, using default (insecure)"
    export SECRET_KEY="dev-secret-key-change-in-production"
fi

if [ -z "$FLASK_ENV" ]; then
    export FLASK_ENV="development"
fi

if [ -z "$REDIS_URL" ]; then
    export REDIS_URL="redis://localhost:6379/0"
fi

cleanup() {
    echo ""
    echo "Shutting down..."
    kill $CELERY_PID $WEB_PID 2>/dev/null || true
    wait $CELERY_PID $WEB_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

celery -A celery_worker.celery worker --loglevel=info --queues=celery,pathfinding,health,maintenance &
CELERY_PID=$!

sleep 2

if [ "$FLASK_ENV" = "production" ]; then
    gunicorn --bind 0.0.0.0:9020 run:app &
else
    python run.py &
fi
WEB_PID=$!

sleep 1

echo "Server:  http://localhost:9020"
echo "Swagger: http://localhost:9020/api/docs"
echo "Press Ctrl+C to stop"

wait $CELERY_PID $WEB_PID
