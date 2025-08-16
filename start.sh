#!/bin/bash

# Iris Web Backend Startup Script
# Starts both Flask web server and Celery worker

set -e  # Exit on any error

echo "🚀 Starting Iris Web Backend..."

# Redis connectivity will be verified when the application starts

# Check required environment variables
if [ -z "$SECRET_KEY" ]; then
    echo "⚠️  WARNING: SECRET_KEY not set, using default (not secure for production)"
    export SECRET_KEY="dev-secret-key-change-in-production"
fi

if [ -z "$FLASK_ENV" ]; then
    echo "⚠️  Setting FLASK_ENV to development"
    export FLASK_ENV="development"
fi

if [ -z "$REDIS_URL" ]; then
    echo "⚠️  Setting REDIS_URL to default"
    export REDIS_URL="redis://localhost:6379/0"
fi

echo "🔧 Environment configured"

# Function to cleanup background processes on exit
cleanup() {
    echo ""
    echo "🔄 Shutting down services..."
    kill $CELERY_PID $WEB_PID 2>/dev/null || true
    wait $CELERY_PID $WEB_PID 2>/dev/null || true
    echo "✅ Services stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

echo "🔄 Starting Celery worker..."
# Start Celery worker in background with all required queues
celery -A celery_worker.celery worker --loglevel=info --queues=celery,pathfinding,health,maintenance &
CELERY_PID=$!

# Give Celery a moment to start
sleep 2

echo "🔄 Starting Flask web server..."
# Start web server in background
if [ "$FLASK_ENV" = "production" ]; then
    gunicorn --bind 0.0.0.0:9020 run:app &
else
    python run.py &
fi
WEB_PID=$!

# Give web server a moment to start
sleep 2

echo ""
echo "🎉 Iris Web Backend is running!"
echo "   📡 Web Server: http://localhost:9020"
echo "   👷 Celery Worker: Running (PID: $CELERY_PID)"
echo "   🌐 Web Process: Running (PID: $WEB_PID)"
echo ""
echo "📚 API Documentation: http://localhost:9020/"
echo "🏥 Health Check: http://localhost:9020/health"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for both processes
wait $CELERY_PID $WEB_PID