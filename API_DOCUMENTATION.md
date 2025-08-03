# Iris Wikipedia Pathfinder API Documentation

## Overview

The Iris Wikipedia Pathfinder API finds the shortest path between two Wikipedia pages using an optimized Redis-based BFS algorithm. The API is built with Flask and uses Celery for asynchronous task processing.

## Base URL

```
http://localhost:9020
```

## Quick Start

### 1. Quick Start (One Command)

The easiest way to run the application:

```bash
# Clone and setup
git clone <repository-url>
cd iris-web-backend

# Create virtual environment
python3 -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# One command to start everything (development)
./dev.sh
```

The `dev.sh` script will:
- Set up development environment variables
- Start Redis if not running
- Launch both Flask server and Celery worker
- Handle graceful shutdown with Ctrl+C

### 2. Production Deployment

For production, use the main startup script:

```bash
# Set environment variables
export FLASK_ENV=production
export SECRET_KEY=your-secure-secret-key
export REDIS_URL=redis://localhost:6379/0

# Start everything
./start.sh
```

### 3. Manual Setup (Alternative)

If you prefer to start services manually:

```bash
# Set environment variables
export FLASK_ENV=development
export SECRET_KEY=your-secret-key-here
export REDIS_URL=redis://localhost:6379/0

# Start Redis server (required)
redis-server

# Start Flask application (Terminal 1)
python run.py

# Start Celery worker (Terminal 2)
celery -A celery_worker.celery worker --loglevel=info --queues=celery,pathfinding,health,maintenance
```

### 4. Using with Process Managers

The application includes a Procfile

**Procfile**
```
web: gunicorn --bind 0.0.0.0:9020 run:app
worker: celery -A celery_worker.celery worker --loglevel=info
```

Usage:
```bash
# Using separate processes (recommended for production platforms)
foreman start

# Using Heroku (automatically uses Procfile)
git push heroku main

# Using honcho
honcho start
```

## API Endpoints

### 1. Root Endpoint - API Information

**GET /**

Returns basic API information and available endpoints.

**Response:**
```json
{
  "name": "Iris Wikipedia Pathfinder API",
  "version": "2.0.0",
  "description": "Find shortest paths between Wikipedia pages",
  "endpoints": {
    "POST /getPath": "Start pathfinding between two pages",
    "GET /tasks/status/<task_id>": "Check task status",
    "POST /explore": "Explore page connections",
    "GET /health": "Health check",
    "GET /": "API information"
  },
  "documentation": "./API_DOCUMENTATION.md"
}
```

### 2. Find Path Between Pages

**POST /getPath**

Initiates pathfinding between two Wikipedia pages. Returns a task ID for polling the result.

**Request Body:**
```json
{
  "start": "Albert Einstein",
  "end": "Physics",
  "max_depth": 6,
  "algorithm": "bfs"
}
```

**Request Parameters:**
- `start` (string, required): Starting Wikipedia page title
- `end` (string, required): Target Wikipedia page title  
- `max_depth` (integer, optional): Maximum search depth (1-10, default: 6)
- `algorithm` (string, optional): Search algorithm ("bfs" or "bidirectional", default: "bfs")

**Response (202 Accepted):**
```json
{
  "status": "IN_PROGRESS",
  "task_id": "abc123-def456-ghi789",
  "poll_url": "/tasks/status/abc123-def456-ghi789",
  "start_page": "Albert Einstein",
  "end_page": "Physics"
}
```

**Example cURL:**
```bash
curl -X POST http://localhost:9020/getPath \
  -H "Content-Type: application/json" \
  -d '{
    "start": "Albert Einstein",
    "end": "Physics",
    "max_depth": 6
  }'
```

### 3. Check Task Status

**GET /tasks/status/{task_id}**

Polls the status of a pathfinding task.

**Path Parameters:**
- `task_id` (string, required): Task ID returned from /getPath

**Response - Task Pending:**
```json
{
  "status": "PENDING", 
  "task_id": "abc123-def456-ghi789",
  "message": "Task is waiting to be processed"
}
```

**Response - Task In Progress:**
```json
{
  "status": "IN_PROGRESS",
  "task_id": "abc123-def456-ghi789", 
  "progress": {
    "current_depth": 3,
    "nodes_explored": 150,
    "message": "Searching at depth 3..."
  }
}
```

**Response - Task Success:**
```json
{
  "status": "SUCCESS",
  "task_id": "abc123-def456-ghi789",
  "result": {
    "path": ["Albert Einstein", "Science", "Physics"],
    "length": 3,
    "search_time": 2.45,
    "nodes_explored": 287
  }
}
```

**Response - Task Failed:**
```json
{
  "status": "FAILURE",
  "task_id": "abc123-def456-ghi789",
  "error": "No path found between pages within maximum depth"
}
```

**Example cURL:**
```bash
curl http://localhost:9020/tasks/status/abc123-def456-ghi789
```

### 4. Explore Page Connections

**POST /explore**

Explores connections from a Wikipedia page for visualization purposes.

**Request Body:**
```json
{
  "start": "Albert Einstein",
  "max_links": 15
}
```

**Request Parameters:**
- `start` (string, required): Wikipedia page title to explore
- `max_links` (integer, optional): Maximum number of links to return (1-50, default: 10)

**Response (200 OK):**
```json
{
  "start_page": "Albert Einstein",
  "nodes": [
    "Albert Einstein",
    "Physics", 
    "Mathematics",
    "Germany",
    "Nobel Prize"
  ],
  "edges": [
    ["Albert Einstein", "Physics"],
    ["Albert Einstein", "Mathematics"], 
    ["Albert Einstein", "Germany"],
    ["Albert Einstein", "Nobel Prize"]
  ],
  "total_links": 156
}
```

**Example cURL:**
```bash
curl -X POST http://localhost:9020/explore \
  -H "Content-Type: application/json" \
  -d '{
    "start": "Albert Einstein",
    "max_links": 10
  }'
```

### 5. Health Check

**GET /health**

Checks the health status of all system components.

**Response - Healthy (200 OK):**
```json
{
  "status": "healthy",
  "redis_status": "healthy",
  "cache_status": "healthy", 
  "wikipedia_api_status": "healthy",
  "timestamp": "2025-01-31T00:00:00Z"
}
```

**Response - Degraded (503 Service Unavailable):**
```json
{
  "status": "degraded",
  "redis_status": "unhealthy: Connection refused",
  "cache_status": "healthy",
  "wikipedia_api_status": "healthy", 
  "timestamp": "2025-01-31T00:00:00Z"
}
```

**Example cURL:**
```bash
curl http://localhost:9020/health
```

### 6. Clear Cache (Admin)

**POST /cache/clear**

Clears cached data (admin endpoint).

**Request Body:**
```json
{
  "pattern": "wiki_links:*"
}
```

**Request Parameters:**
- `pattern` (string, optional): Redis key pattern to clear (default: "wiki_links:*")

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Cleared 1,245 cache entries",
  "pattern": "wiki_links:*"
}
```

**Example cURL:**
```bash
curl -X POST http://localhost:9020/cache/clear \
  -H "Content-Type: application/json" \
  -d '{"pattern": "wiki_links:*"}'
```

## Error Responses

All endpoints return structured error responses when something goes wrong:

**400 Bad Request - Validation Error:**
```json
{
  "error": true,
  "message": "Validation failed: {'start': ['Start page is required']}",
  "code": "VALIDATION_ERROR"
}
```

**404 Not Found:**
```json
{
  "error": true,
  "message": "Endpoint not found",
  "code": "NOT_FOUND"
}
```

**405 Method Not Allowed:**
```json
{
  "error": true,
  "message": "Method not allowed", 
  "code": "METHOD_NOT_ALLOWED"
}
```

**500 Internal Server Error:**
```json
{
  "error": true,
  "message": "Internal server error",
  "code": "INTERNAL_ERROR"
}
```

## Complete Example Workflow

Here's a complete example of finding a path between two Wikipedia pages:

### Step 1: Start the pathfinding task

```bash
curl -X POST http://localhost:9020/getPath \
  -H "Content-Type: application/json" \
  -d '{
    "start": "Barack Obama",
    "end": "Computer Science"
  }'
```

**Response:**
```json
{
  "status": "IN_PROGRESS",
  "task_id": "xyz789-abc123-def456",
  "poll_url": "/tasks/status/xyz789-abc123-def456", 
  "start_page": "Barack Obama",
  "end_page": "Computer Science"
}
```

### Step 2: Poll for task completion

```bash
curl http://localhost:9020/tasks/status/xyz789-abc123-def456
```

**First response (task still running):**
```json
{
  "status": "IN_PROGRESS",
  "task_id": "xyz789-abc123-def456",
  "progress": {
    "current_depth": 2,
    "nodes_explored": 95,
    "message": "Searching at depth 2..."
  }
}
```

**Final response (task completed):**
```json
{
  "status": "SUCCESS", 
  "task_id": "xyz789-abc123-def456",
  "result": {
    "path": [
      "Barack Obama",
      "Harvard University", 
      "MIT",
      "Computer Science"
    ],
    "length": 4,
    "search_time": 3.2,
    "nodes_explored": 342
  }
}
```

## Rate Limiting

The API includes basic rate limiting middleware:
- Default: 100 requests per minute per IP
- Rate limit headers are included in responses
- Exceeding limits returns HTTP 429 Too Many Requests

## Environment Configuration

### Required Environment Variables

```bash
export SECRET_KEY=your-secret-key-here
export FLASK_ENV=development  # or production
export REDIS_URL=redis://localhost:6379/0
```

### Optional Configuration

```bash
export MAX_SEARCH_DEPTH=6           # Maximum BFS search depth
export BFS_BATCH_SIZE=50           # Wikipedia API batch size
export WIKIPEDIA_MAX_WORKERS=10     # HTTP thread pool size
export CACHE_TTL=86400             # Cache TTL in seconds
export LOG_LEVEL=INFO              # Logging level
```

## Testing

### Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run unit tests only
pytest tests/unit/ -v

# Run integration tests only
pytest tests/integration/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html
```

### Test the API

```bash
# Test basic functionality
curl http://localhost:9020/
curl http://localhost:9020/health

# Test pathfinding
curl -X POST http://localhost:9020/getPath \
  -H "Content-Type: application/json" \
  -d '{"start": "Python", "end": "Computer"}'
```

## Architecture Notes

- **Asynchronous Processing**: All pathfinding runs as background Celery tasks
- **Redis-Based BFS**: Memory-efficient algorithm using Redis queues
- **Scalable**: Can handle large search spaces without memory issues
- **Error Handling**: Comprehensive error handling with structured responses
- **Caching**: Intelligent caching of Wikipedia API responses
- **Health Monitoring**: Built-in health checks for all components

## Dependencies

- Flask: Web framework
- Celery: Asynchronous task queue
- Redis: In-memory data store and message broker
- Marshmallow: Request/response validation
- Requests: HTTP client for Wikipedia API
- Pytest: Testing framework

## Support

For issues and questions:
- Check the logs: Application logs provide detailed error information
- Health endpoint: Use `/health` to diagnose system issues
- Redis connectivity: Ensure Redis is running and accessible
- Wikipedia API: Check if Wikipedia API is accessible from your network