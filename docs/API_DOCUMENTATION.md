# Iris Wikipedia Pathfinder API Documentation

## Overview

The Iris Wikipedia Pathfinder API finds the shortest path between two Wikipedia pages using an optimized Redis-based BFS algorithm. The API is built with Flask and uses Celery for asynchronous task processing. It includes an interactive web interface for real-time graph visualization.

## Base URL

```
Application: http://localhost:9020
Interactive UI: http://localhost:9020 (default landing page)
API Documentation: http://localhost:9020/api
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

**Procfile:**
```
web: ./start.sh
```

**Usage:**
```bash
# For production
foreman start

# Using Heroku (automatically uses Procfile)
git push heroku main

# Using honcho
honcho start
```

## API Endpoints

### 1. Interactive UI (Landing Page)

**GET /**

Serves the interactive web interface for pathfinding visualization (default landing page).

**GET /any-path**

All non-API paths automatically redirect to the main UI for a seamless user experience.

### 2. API Information

**GET /api**

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
    "GET /": "Interactive web interface",
    "GET /api": "API information"
  },
  "documentation": "./API_DOCUMENTATION.md",
  "ui_url": "/"
}
```

### 3. Find Path Between Pages

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

### 4. Check Task Status

**GET /tasks/status/{task_id}**

Polls the status of a pathfinding task.

**Path Parameters:**
- `task_id` (string, required): Task ID returned from /getPath

**Response — PENDING:**
```json
{
  "status": "PENDING",
  "task_id": "abc123-def456-ghi789",
  "message": "Task is waiting to be processed"
}
```

**Response — IN_PROGRESS:**
```json
{
  "status": "IN_PROGRESS",
  "task_id": "abc123-def456-ghi789",
  "progress": {
    "status": "Starting pathfinding search...",
    "search_stats": {
      "nodes_explored": 0,
      "current_depth": 0,
      "last_node": "Albert Einstein",
      "queue_size": 1,
      "start_page": "Albert Einstein",
      "end_page": "Physics",
      "max_depth": 6
    },
    "search_time_elapsed": 0
  }
}
```

Note: The `progress` object mirrors the task's meta and may include additional fields depending on runtime.

**Response — SUCCESS:**
```json
{
  "status": "SUCCESS",
  "task_id": "abc123-def456-ghi789",
  "result": {
    "path": ["Albert Einstein", "Science", "Physics"],
    "length": 3,
    "search_time": 2.45,
    "nodes_explored": 287,
    "search_stats": {
      "nodes_explored": 287,
      "final_depth": 2,
      "start_page": "Albert Einstein",
      "end_page": "Physics",
      "max_depth": 6,
      "search_completed": true
    }
  }
}
```

Note: If the underlying task returns a different structure, it may be passed through as-is in `result`.

**Response — FAILURE:**
```json
{
  "status": "FAILURE",
  "task_id": "abc123-def456-ghi789",
  "error": "No path found between pages within maximum depth"
}
```

**Response — Other States (e.g., RETRY):**
```json
{
  "status": "RETRY",
  "task_id": "abc123-def456-ghi789",
  "info": "Retrying due to: Connection timeout to Wikipedia API"
}
```

Note: For states other than the above, `info` contains a string description derived from the task's state/meta.

**Example cURL:**
```bash
curl http://localhost:9020/tasks/status/abc123-def456-ghi789
```

### 5. Explore Page Connections

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

### 6. Health Check

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

### 7. Clear Cache (Admin)

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

### 8. Interactive Web Interface Features

The main landing page (`/`) serves the interactive web interface with enhanced features:

**Enhanced Features:**
- **UI-First Experience**: Landing page serves interactive UI directly, all paths redirect to main interface
- **State Persistence**: Automatically saves and restores search state using localStorage
- **Mobile-Optimized**: Fixed touch/scroll conflicts for seamless mobile graph interaction
- **Session Recovery**: Automatically resumes interrupted searches after page refresh
- **Modern Dark Theme**: Professional dark tech aesthetic with GitHub-inspired colors
- **Interactive Graph Visualization**: D3.js-powered force-directed graph with physics simulation
- **Dynamic Node Interaction**: Drag-and-drop nodes with intelligent physics
- **Smart Text Rendering**: Dynamic text truncation based on graph density
- **Professional Typography**: JetBrains Mono font throughout
- **Responsive Design**: Works perfectly on desktop and mobile devices

**Navigation:**
```
http://localhost:9020/       (default landing page)
http://localhost:9020/ui     (redirects to main UI)
http://localhost:9020/<any>  (redirects to main UI)
```

**Interface Components:**
- **Input Section**: Start and end page input fields with validation
- **Control Buttons**: Find Path and Clear buttons with full-width responsive layout
- **Graph Visualization**: Interactive D3.js graph with:
  - Tightly bound physics simulation
  - Opaque text backgrounds for readability
  - Centered directional arrows on edges
  - Color-coded nodes (start: green, end: red, path: blue)
- **Path Results**: Step-by-step path display with clickable Wikipedia links
- **Error Handling**: User-friendly error messages and loading states

**Usage:**
1. Navigate to `/` in your browser (or any non-API path)
2. Enter Wikipedia page titles in start and end fields  
3. Click "Find Path" to initiate pathfinding
4. View graph visualization as path is discovered
5. Interact with nodes by dragging them (mobile-optimized)
6. Click on path steps to visit Wikipedia pages
7. State is automatically saved - refresh to resume interrupted searches

**Technical Details:**
- Uses D3.js v7 for graph visualization
- Implements custom physics simulation with collision detection
- Automatic text truncation based on node spacing
- WebSocket-like polling for real-time updates
- Mobile-responsive CSS Grid layout

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

Note: JSON 404 responses are returned for API-like paths (for example, `/api/...`).
Requests to non-API paths instead redirect to the main UI (`/`).

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
    "current": 10,
    "total": 100,
    "status": "Validating pages...",
    "start_page": "Barack Obama",
    "end_page": "Computer Science"
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

Basic logging-only rate limiting is present for visibility, but limits are not enforced in this build:
- Logs each request with a per-IP note; no counters are persisted
- No `429 Too Many Requests` responses are emitted by default
- For production-grade limits, plug in a Redis-backed limiter

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
