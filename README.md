<p align="center">
<a href="https://dscvit.com">
	<img src="https://user-images.githubusercontent.com/30529572/72455010-fb38d400-37e7-11ea-9c1e-8cdeb5f5906e.png" />
</a>
	<h2 align="center">Iris Wikipedia Pathfinder</h2>
	<h4 align="center">Find shortest paths between Wikipedia pages using Redis-based BFS</h4>
</p>

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.1.1-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Redis](https://img.shields.io/badge/Redis-6.2.0-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io)
[![Celery](https://img.shields.io/badge/Celery-5.5.3-37B24D?style=for-the-badge&logo=celery&logoColor=white)](https://docs.celeryproject.org/)
[![Gunicorn](https://img.shields.io/badge/Gunicorn-23.0.0-499848?style=for-the-badge&logo=gunicorn&logoColor=white)](https://gunicorn.org/)

[![D3.js](https://img.shields.io/badge/D3.js-Graph%20Visualization-F9A03C?style=for-the-badge&logo=d3.js&logoColor=white)](https://d3js.org/)
[![pytest](https://img.shields.io/badge/pytest-8.3.3-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)](https://pytest.org)
[![Ruff](https://img.shields.io/badge/Code%20Style-Ruff-D7FF64?style=for-the-badge&logo=ruff&logoColor=black)](https://github.com/astral-sh/ruff)
[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](./LICENSE)

## Quick Start

```bash
git clone <repository-url>
cd iris-web-backend

python3 -m venv env && source env/bin/activate
pip install -r requirements.txt

./dev.sh   # starts Redis + Flask + Celery; server at http://localhost:9020
```

## Scripts

| Script | Purpose |
|--------|---------|
| `dev.sh` | Local development — starts Redis (if needed), Flask dev server, and Celery worker |
| `start.sh` | Manual production-like startup on a single host (both web + worker) |
| `entrypoint.sh` | Docker/Railway container entrypoint — switches on `SERVICE_TYPE` env var |

## API

Interactive documentation at `/api/docs` (Swagger UI).

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web UI |
| `/getPath` | POST | Start pathfinding — returns `task_id` |
| `/tasks/status/<id>` | GET | Poll task status and progress |
| `/explore` | POST | Explore page connections for graph viz |
| `/health` | GET | System health check |
| `/api` | GET | API info |
| `/api/docs` | GET | Swagger UI |

## Development

```bash
pytest -v          # run tests
ruff format .      # format
ruff check .       # lint
```

## Contributors

- **Md Hishaam Akhtar** — [GitHub](https://github.com/mdhishaamakhtar) | [LinkedIn](https://www.linkedin.com/in/md-hishaam-akhtar-812a3019a/)
- **Sharanya Mukherjee** — [GitHub](https://github.com/sharanya02) | [LinkedIn](https://www.linkedin.com/in/sharanya-mukherjee-73a2061a0/)

<p align="center">
	Made with :heart: by <a href="https://dscvit.com">DSC VIT</a>
</p>
