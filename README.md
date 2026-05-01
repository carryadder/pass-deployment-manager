# Deployment Manager

Day 17 foundation for a self-hosted deployment manager.

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

Frontend quick start:

```bash
cd frontend
npm install
npm run dev
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

- `GET /api/services`
- `GET /api/services/{id}`
- `POST /api/services`
- `POST /api/services/{id}/start`
- `POST /api/services/{id}/stop`
- `POST /api/services/{id}/restart`
- `POST /api/services/{id}/redeploy`
- `DELETE /api/services/{id}`
- `POST /api/services/{id}/deploy`
- `POST /api/services/{id}/rollout`
- `POST /api/services/{id}/rollback`
- `GET /api/services/{id}/env`
- `POST /api/services/{id}/env`
- `PUT /api/services/{id}/env/{key}`
- `DELETE /api/services/{id}/env/{key}`
- `GET /api/services/{id}/metrics?range=5m`
- `GET /api/services/{id}/deploys`
- `GET /api/services/deploys/{deploy_id}/logs`
- `WS /api/services/{id}/logs?tail=200&follow=true`
- `WS /api/services/{id}/metrics?range=5m`

Volume and network endpoints:

- `GET /api/volumes`
- `POST /api/volumes`
- `DELETE /api/volumes/{name}`
- `GET /api/networks`
- `POST /api/networks`
- `DELETE /api/networks/{name}`

Frontend tooling:

- `npm run dev`
- `npm run build`
- `npm run generate:api`

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
- Optional `healthcheck` supports `http`, `tcp`, or `cmd` checks and is translated into Docker healthcheck config.
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
  "domain": "hello.localhost",
  "healthcheck": {
    "type": "http",
    "value": "http://127.0.0.1/healthz"
  }
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

## Metrics

- The in-process sampler polls Docker stats every `METRICS_SAMPLE_INTERVAL_SECONDS` seconds and keeps `METRICS_MAX_SAMPLES` points per service in memory.
- `GET /api/services/{id}/metrics?range=5m` returns recent CPU, memory, network, block I/O, and pid samples.
- `WS /api/services/{id}/metrics?range=5m` sends recent history first, then streams new samples live.

## Health Monitoring

- Service create now accepts a Docker healthcheck definition and passes it through to the container runtime.
- A background Docker event watcher listens for `health_status: unhealthy` and `die` events for managed services.
- Non-zero exits and unhealthy events update service state and append audit entries; restartable services also get a recovery attempt.

## Volumes And Networks

- Volume list responses now include driver, mountpoint, labels, options, and Docker-reported usage fields when available.
- Network list responses now include driver, scope, labels, internal/attachable flags, options, and attached container counts.
- `POST /api/volumes` and `POST /api/networks` create reusable resources for the service form.
- `DELETE /api/volumes/{name}` and `DELETE /api/networks/{name}` remove those resources when they are no longer needed.

## Frontend

- `frontend/` now contains a Vite + React + TypeScript + Tailwind bootstrap with TanStack Query and Zustand.
- The checked-in UI now includes a login screen, persisted auth session, protected shell layout, and a service dashboard with search, create, and action controls.
- Service detail pages now live at `/services/{id}` with tabs for Overview, Logs, Metrics, Env, Volumes, Settings, and Deploys.
- A generated-client path is prepared via `npm run generate:api`, and the scaffold already includes a minimal generated-style API layer for auth and inventory endpoints.

## Traefik

- `docker-compose.yml` now provisions Traefik with the Docker provider and ACME storage.
- Public services join the `${TRAEFIK_PUBLIC_NETWORK}` bridge automatically so Traefik can reach them.
- Real domains use HTTPS with the configured ACME resolver.
- `*.localhost` also gets Traefik routing; Traefik serves its default self-signed certificate on `https://<service>.localhost`.

## Logs

- The service logs websocket accepts either an `Authorization: Bearer <token>` header or `?token=<jwt>` query parameter.
- `tail` controls the initial backlog size and `follow=true` keeps streaming new log lines.
