<p align="center">
<a href="https://dscvit.com">
	<img src="https://user-images.githubusercontent.com/30529572/72455010-fb38d400-37e7-11ea-9c1e-8cdeb5f5906e.png" />
</a>
	<h2 align="center">Iris Wikipedia Pathfinder</h2>
	<h4 align="center">A high-performance service for discovering shortest paths between Wikipedia pages using optimized graph algorithms</h4>
</p>


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

### ✅ Interactive Visualization
- **Web-Based UI**: Modern dark-themed interface for interactive pathfinding
- **Real-Time Graph Visualization**: D3.js-powered interactive graph with physics simulation
- **Dynamic Features**: Drag-and-drop nodes, responsive layout, smart text truncation
- **Professional Design**: Clean typography with JetBrains Mono, opaque text backgrounds

### ✅ Development Tools
- **Comprehensive Testing**: Unit and integration tests with 100% pass rate
- **Environment Management**: Separate configurations for development, testing, and production
- **CI/CD Ready**: GitHub Actions integration for automated testing and deployment

## Core Technologies

[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1.1-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Redis](https://img.shields.io/badge/Redis-6.2.0-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![Celery](https://img.shields.io/badge/Celery-5.5.3-37B24D?style=for-the-badge&logo=celery&logoColor=white)](https://docs.celeryproject.org/)
[![Gunicorn](https://img.shields.io/badge/Gunicorn-23.0.0-499848?style=for-the-badge&logo=gunicorn&logoColor=white)](https://gunicorn.org/)

## Frontend & Visualization

[![D3.js](https://img.shields.io/badge/D3.js-Graph%20Visualization-F9A03C?style=for-the-badge&logo=d3.js&logoColor=white)](https://d3js.org/)
[![JetBrains Mono](https://img.shields.io/badge/Typography-JetBrains%20Mono-000000?style=for-the-badge&logo=jetbrains&logoColor=white)](https://www.jetbrains.com/lp/mono/)
[![Dark Theme](https://img.shields.io/badge/UI-Dark%20Tech%20Theme-161B22?style=for-the-badge&logo=github&logoColor=white)](#)
[![Interactive](https://img.shields.io/badge/UX-Interactive%20Physics-58A6FF?style=for-the-badge&logo=react&logoColor=white)](#)

## Development & Testing

[![pytest](https://img.shields.io/badge/pytest-8.3.3-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)](https://pytest.org)
[![Black](https://img.shields.io/badge/Code%20Style-Black-000000?style=for-the-badge&logo=python&logoColor=white)](https://github.com/psf/black)
[![Coverage](https://img.shields.io/badge/Coverage-81%20Tests%20Passing-success?style=for-the-badge&logo=pytest)](./tests/)
[![Marshmallow](https://img.shields.io/badge/Validation-Marshmallow-FF6B6B?style=for-the-badge&logo=python)](https://marshmallow.readthedocs.io/)

## Project Information

[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](./LICENSE)
[![GDSC VIT](https://img.shields.io/badge/GDSC-VIT-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://dscvit.com)
[![Documentation](https://img.shields.io/badge/Documentation-API%20Docs-green?style=for-the-badge&logo=gitbook&logoColor=white)](./API_DOCUMENTATION.md)

## Infrastructure

[![Wikipedia API](https://img.shields.io/badge/Wikipedia-API-000000?style=for-the-badge&logo=wikipedia&logoColor=white)](https://www.mediawiki.org/wiki/API:Main_page)
[![Graph Theory](https://img.shields.io/badge/Algorithm-BFS%20Graph%20Search-FF6B35?style=for-the-badge&logo=graphql&logoColor=white)](./README.md)

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

The application will be available at:
- **API**: `http://localhost:9020`
- **Interactive UI**: `http://localhost:9020/ui`

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
- `GET /ui` - Interactive web interface for pathfinding visualization

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

## Contributors

This project was developed by:

- **Md Hishaam Akhtar** - [GitHub](https://github.com/mdhishaamakhtar) | [LinkedIn](https://www.linkedin.com/in/md-hishaam-akhtar-812a3019a/)
- **Sharanya Mukherjee** - [GitHub](https://github.com/sharanya02) | [LinkedIn](https://www.linkedin.com/in/sharanya-mukherjee-73a2061a0/)

<p align="center">
	Made with :heart: by <a href="https://dscvit.com">DSC VIT</a>
</p>
