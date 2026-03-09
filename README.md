<!-- markdownlint-disable MD033 -->

<p align="center">
  <a href="https://dscvit.com">
    <img src="https://user-images.githubusercontent.com/30529572/72455010-fb38d400-37e7-11ea-9c1e-8cdeb5f5906e.png" width="120" />
  </a>
</p>

## Iris Wikipedia Pathfinder

Iris finds the shortest path between any two Wikipedia pages by traversing their links.

You give it two page titles — say, "Octopus" and "Adolf Hitler" — and it walks Wikipedia's link graph using BFS until it finds the connection. Results are visualized as an interactive graph you can drag around.

It uses Redis to store the BFS state instead of holding everything in memory, which keeps it from blowing up on deep searches.

## What It Does

- Find shortest Wikipedia paths via Redis-based BFS
- Async task processing — searches run in the background, results polled live
- Real-time progress updates during search
- Interactive D3.js graph visualization of the path
- Explore page connections for arbitrary graph visualization
- Persistent search state — page refreshes resume from where you left off

## Tech Stack

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Celery](https://img.shields.io/badge/Celery-5.5-37B24D?style=for-the-badge&logo=celery&logoColor=white)](https://docs.celeryproject.org/)
[![Redis](https://img.shields.io/badge/Redis-6-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![Gunicorn](https://img.shields.io/badge/Gunicorn-23-499848?style=for-the-badge&logo=gunicorn&logoColor=white)](https://gunicorn.org/)
[![D3.js](https://img.shields.io/badge/D3.js-Graph%20Viz-F9A03C?style=for-the-badge&logo=d3.js&logoColor=white)](https://d3js.org/)
[![Ruff](https://img.shields.io/badge/Ruff-lint%20%2B%20format-D7FF64?style=for-the-badge&logo=ruff&logoColor=black)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](./LICENSE)

## Quick Start

```bash
git clone https://github.com/mdhishaamakhtar/wikiweb-backend
cd iris-web-backend

python3 -m venv env && source env/bin/activate
pip install -r requirements.txt

./dev.sh
```

Then open [http://localhost:9020](http://localhost:9020).

Swagger docs at [http://localhost:9020/api/docs](http://localhost:9020/api/docs).

## Scripts

| Script | When to use |
|--------|-------------|
| `dev.sh` | Local development — starts Redis (if needed), Flask, and Celery in one terminal |
| `start.sh` | Manual production-like run on a single host (both web + worker) |
| `entrypoint.sh` | Docker/Railway container entry — switches on `SERVICE_TYPE` env var |

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/getPath` | Start a pathfinding task, returns `task_id` |
| `GET` | `/tasks/status/<id>` | Poll task status and live progress |
| `POST` | `/explore` | Get outgoing links from a page for graph viz |
| `GET` | `/health` | Redis + cache + Wikipedia API health check |
| `GET` | `/api/docs` | Swagger UI |

## Dev

```bash
pytest -v                                    # run tests
pytest --cov=app --cov-report=term-missing   # run tests with coverage
pytest --cov=app --cov-report=html           # generate HTML coverage report (open htmlcov/index.html)
ruff format .                                # format
ruff check .                                 # lint
```

## Contributors

- **Md Hishaam Akhtar** — [GitHub](https://github.com/mdhishaamakhtar) · [LinkedIn](https://www.linkedin.com/in/md-hishaam-akhtar-812a3019a/)
- **Sharanya Mukherjee** — [GitHub](https://github.com/sharanya02) · [LinkedIn](https://www.linkedin.com/in/sharanya-mukherjee-73a2061a0/)

<p align="center">
  Made with :heart: by <a href="https://dscvit.com">DSC VIT</a>
</p>
