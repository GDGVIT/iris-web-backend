#!/bin/bash

# Development startup script for Iris Web Backend
# Simple one-command startup for local development

echo "🚀 Starting Iris Web Backend (Development Mode)"

# Set development environment
export FLASK_ENV=development
export SECRET_KEY=${SECRET_KEY:-"dev-secret-key-not-secure"}
export REDIS_URL=${REDIS_URL:-"redis://localhost:6379"}

# Check if Redis is running
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis is not running. Starting Redis..."
    redis-server --daemonize yes
    sleep 1
    if ! redis-cli ping > /dev/null 2>&1; then
        echo "❌ Failed to start Redis. Please start it manually: redis-server"
        exit 1
    fi
fi

echo "✅ Redis is running"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🔄 Stopping services..."
    kill $CELERY_PID $WEB_PID 2>/dev/null || true
    wait $CELERY_PID $WEB_PID 2>/dev/null || true
    echo "✅ Development server stopped"
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "🔄 Starting Celery worker..."
celery -A celery_worker.celery worker --loglevel=info --queues=celery,pathfinding,health,maintenance &
CELERY_PID=$!

sleep 2

echo "🔄 Starting Flask development server..."
python run.py &
WEB_PID=$!

sleep 2

echo ""
echo "🎉 Development server is running!"
echo "   📡 Server: http://localhost:9020"
echo "   👷 Celery: Running"
echo ""
echo "Press Ctrl+C to stop"

wait $CELERY_PID $WEB_PID