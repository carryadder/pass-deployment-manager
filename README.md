# Deployment Manager

Day 11 foundation for a self-hosted deployment manager.

## Requirements

- Python 3.12+
- Docker Engine running locally
- `uv` installed

## Quick Start

```bash
uv sync
docker compose up -d postgres traefik
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

Auth endpoints:

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`

Service endpoint:

- `POST /api/services`
- `POST /api/services/{id}/deploy`
- `POST /api/services/{id}/rollout`
- `POST /api/services/{id}/rollback`
- `GET /api/services/{id}/env`
- `POST /api/services/{id}/env`
- `PUT /api/services/{id}/env/{key}`
- `DELETE /api/services/{id}/env/{key}`
- `GET /api/services/{id}/deploys`
- `GET /api/services/deploys/{deploy_id}/logs`
- `WS /api/services/{id}/logs?tail=200&follow=true`

## Environment

Copy `.env.example` to `.env` and adjust values if needed.

## Database

- `docker-compose.yml` provisions PostgreSQL for local development.
- `alembic.ini` and `backend/alembic/` contain the Day 4 migration baseline.
- Models live under `backend/app/models/`.

## Auth

- `BOOTSTRAP_ADMIN_EMAIL` and `BOOTSTRAP_ADMIN_PASSWORD` can seed the first owner account on startup.
- `GET /api/auth/me` is protected and should return `401` without a bearer token.

## Service Create

- `POST /api/services` creates a Docker-backed service from an image with CPU, memory, port, volume, and network settings.
- Set `domain` in the payload to attach Traefik labels automatically.
- The first service for a user is attached to an auto-created personal project until project CRUD arrives.

Example:

```json
{
  "name": "hello",
  "image": "nginx:latest",
  "cpus": 0.5,
  "memory_mb": 256,
  "ports": [
    {"container_port": 80}
  ],
  "domain": "hello.localhost"
}
```

## Git Builds

- `POST /api/services/{id}/deploy` queues a background Git clone and Docker image build.
- Build images are tagged as `dmgr/{service_slug}:{short_ref}`.
- `GET /api/services/deploys/{deploy_id}/logs` returns the accumulated build log lines for the queued job.

## Rollout

- `POST /api/services/{id}/rollout` promotes the latest built image into a running container.
- If published host ports would conflict, the old container is stopped first; otherwise the candidate starts alongside it and is promoted after readiness passes.
- `POST /api/services/{id}/rollback` reuses the previously active image when one is available.

## Env And Secrets

- `GET /api/services/{id}/env` lists saved env entries; secret values are masked from API responses.
- `POST`, `PUT`, and `DELETE` on `/api/services/{id}/env...` accept `apply=true` by default and queue a redeploy of the current image so changes reach the running container.
- Secret values are encrypted at rest with the `FERNET_SECRET_KEY` setting before they are stored in the `secrets` table.

## Traefik

- `docker-compose.yml` now provisions Traefik with the Docker provider and ACME storage.
- Public services join the `${TRAEFIK_PUBLIC_NETWORK}` bridge automatically so Traefik can reach them.
- Real domains use HTTPS with the configured ACME resolver.
- `*.localhost` also gets Traefik routing; Traefik serves its default self-signed certificate on `https://<service>.localhost`.

## Logs

- The service logs websocket accepts either an `Authorization: Bearer <token>` header or `?token=<jwt>` query parameter.
- `tail` controls the initial backlog size and `follow=true` keeps streaming new log lines.
