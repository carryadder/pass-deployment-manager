# Deployment Manager

Day 4 foundation for a self-hosted deployment manager.

## Requirements

- Python 3.12+
- Docker Engine running locally
- `uv` installed

## Quick Start

```bash
uv sync
docker compose up -d postgres
uv run alembic upgrade head
uv run uvicorn backend.app.main:app --reload
```

To smoke test the database layer after migrating, open a `uv run python` session and insert a `User` through `Session(engine)`.

Then visit:

- `http://127.0.0.1:8000/healthz`
- `http://127.0.0.1:8000/api/system/info`
- `http://127.0.0.1:8000/api/containers`
- `http://127.0.0.1:8000/api/images`
- `http://127.0.0.1:8000/api/volumes`
- `http://127.0.0.1:8000/api/networks`

Lifecycle actions:

- `POST /api/containers/{id}/start`
- `POST /api/containers/{id}/stop`
- `POST /api/containers/{id}/restart`
- `POST /api/containers/{id}/kill`
- `POST /api/containers/{id}/pause`
- `POST /api/containers/{id}/unpause`
- `DELETE /api/containers/{id}?force=true&volumes=true`
- `DELETE /api/images/{id}?force=true`
- `POST /api/system/prune`

## Environment

Copy `.env.example` to `.env` and adjust values if needed.

## Database

- `docker-compose.yml` provisions PostgreSQL for local development.
- `alembic.ini` and `backend/alembic/` contain the Day 4 migration baseline.
- Models live under `backend/app/models/`.
