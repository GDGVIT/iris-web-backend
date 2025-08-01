<p align="center">
<a href="https://dscvit.com">
	<img src="https://user-images.githubusercontent.com/30529572/72455010-fb38d400-37e7-11ea-9c1e-8cdeb5f5906e.png" />
</a>
	<h2 align="center">Iris Wikipedia Pathfinder</h2>
	<h4 align="center">A high-performance service for discovering shortest paths between Wikipedia pages using optimized graph algorithms</h4>
</p>

---
[![DOCS](https://img.shields.io/badge/Documentation-API%20Documentation-green?style=flat-square&logo=appveyor)](./API_DOCUMENTATION.md)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=flat-square&logo=python)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-Web%20Framework-lightgrey?style=flat-square&logo=flask)](https://flask.palletsprojects.com)
[![Redis](https://img.shields.io/badge/Redis-Cache%20%26%20Queue-red?style=flat-square&logo=redis)](https://redis.io)

## Overview

Iris Wikipedia Pathfinder is a sophisticated web service that implements advanced graph traversal algorithms to find the shortest path between any two Wikipedia pages. Built with modern software architecture principles, the system leverages Redis-based breadth-first search (BFS) algorithms to efficiently navigate Wikipedia's link graph while maintaining scalability and performance.

The project demonstrates expertise in:
- **Domain-Driven Design**: Clean separation between API, business logic, and infrastructure layers
- **Distributed Systems**: Redis-based queuing and caching for horizontal scalability  
- **Asynchronous Processing**: Celery task queues for non-blocking pathfinding operations
- **Algorithm Optimization**: Memory-efficient BFS implementation using external storage
- **Production-Ready Architecture**: Comprehensive error handling, monitoring, and deployment automation

## Core Features

### ✅ Pathfinding Algorithms
- **Redis-Based BFS**: Memory-efficient pathfinding using external Redis queues
- **Configurable Depth Limits**: Prevents infinite searches with customizable depth constraints
- **Batch Processing**: Optimized Wikipedia API usage through intelligent batching

### ✅ Scalable Architecture  
- **Asynchronous Task Processing**: Non-blocking operations using Celery workers
- **Distributed Caching**: Redis-based caching for Wikipedia API responses
- **Session Isolation**: Concurrent searches with isolated Redis namespaces
- **Auto-cleanup**: Automatic resource cleanup to prevent memory accumulation

### ✅ Production Features
- **Health Monitoring**: Comprehensive system health checks and metrics
- **Error Handling**: Structured exception hierarchy with detailed error responses
- **API Validation**: Request/response validation using Marshmallow schemas
- **Rate Limiting**: Configurable API rate limiting for resource protection
- **CORS Support**: Cross-origin resource sharing for frontend integration

### ✅ Development Tools
- **Comprehensive Testing**: Unit and integration tests with 100% pass rate
- **Environment Management**: Separate configurations for development, testing, and production
- **Docker Support**: Containerization for consistent deployments
- **CI/CD Ready**: GitHub Actions integration for automated testing and deployment

## Quick Start

### Development Setup (One Command)
```bash
# Clone and setup
git clone <repository-url>
cd iris-web-backend

# Create virtual environment  
python3 -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start everything (Redis + Flask + Celery)
./dev.sh
```

The application will be available at `http://localhost:9020`

### Production Deployment
```bash
# Set environment variables
export FLASK_ENV=production
export SECRET_KEY=your-secure-secret-key
export REDIS_URL=redis://localhost:6379/0

# Deploy with startup script
./start.sh
```

## API Documentation

Complete API documentation with examples, request/response schemas, and integration guides is available in [API_DOCUMENTATION.md](./API_DOCUMENTATION.md).

### Key Endpoints
- `POST /getPath` - Start pathfinding task (returns task ID for polling)
- `GET /tasks/status/<task_id>` - Poll task status and retrieve results
- `POST /explore` - Discover page connections for graph visualization
- `GET /health` - System health monitoring endpoint

## Architecture Highlights

### Redis-Based BFS Algorithm
The core pathfinding algorithm demonstrates advanced system design:
- **Memory Efficiency**: Uses Redis queues instead of in-memory data structures
- **Horizontal Scalability**: Multiple workers can process different search sessions
- **Session Isolation**: Unique Redis namespaces prevent search interference
- **Automatic Cleanup**: Resource cleanup prevents Redis memory accumulation

### Service Layer Architecture
- **Dependency Injection**: Service factory pattern with proper abstractions
- **Interface Segregation**: Clear contracts between components
- **Error Propagation**: Structured exception handling throughout the stack
- **Configuration Management**: Environment-specific settings with validation

## Testing & Quality Assurance

```bash
# Run comprehensive test suite
pytest tests/ -v

# Run with coverage reporting
pytest tests/ --cov=app --cov-report=html

# Test specific components
pytest tests/unit/ -v      # Unit tests
pytest tests/integration/ -v  # Integration tests
```

Current test coverage: **81 tests passing** with comprehensive unit and integration coverage.

## Technical Implementation Details

For detailed implementation information, development setup, and deployment instructions, see [CLAUDE.md](./CLAUDE.md).

## Contributors

This project was developed by:

- **Md Hishaam Akhtar** - [GitHub](https://github.com/mdhishaamakhtar) | [LinkedIn](https://www.linkedin.com/in/md-hishaam-akhtar-812a3019a/)
- **Sharanya Mukherjee** - [GitHub](https://github.com/sharanya02) | [LinkedIn](https://www.linkedin.com/in/sharanya-mukherjee-73a2061a0/)

## Acknowledgments

<p align="center">
	Developed under the mentorship of <a href="https://dscvit.com">DSC VIT</a>
</p>

---

<p align="center">
	<strong>Iris Wikipedia Pathfinder</strong> - Bridging knowledge through intelligent graph traversal
</p>

