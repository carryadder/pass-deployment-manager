# Deployment Manager — 30-Day Build Plan

A self-hosted, Render-style PaaS for Linux. Deploy any app from a Git repo or Docker image, set CPU / memory / disk limits, get auto-SSL subdomains, manage everything (build, start, stop, restart, rm, rmi, logs, metrics) from a web UI.

Stack: **Python 3.12 + FastAPI uv** backend, **docker-py** for the container engine, **Traefik** for routing & SSL, **PostgreSQL + Redis** for state, **React + Vite** (or HTMX if you want to ship faster) for the UI.

Deadline: **30 days from today (2026-05-01 → 2026-05-30).** Plan assumes ~3 focused hours/day. Each day ships something testable.

---

## 1. Feature scope (researched against Render, Coolify, Dokploy, CapRover)

### Must-have (MVP — covered by this plan)
- **Service lifecycle**: build, start, stop, restart, kill, rm, rmi, prune
- **Resource limits per service**: CPU shares + cpus, memory hard/soft, pids, disk via storage driver, ulimits
- **Live logs**: WebSocket stream of `docker logs -f`, with search & filtering
- **Live metrics**: CPU %, RAM %, network I/O, block I/O sampled from `docker stats`
- **Deploy sources**: (a) Docker image from registry, (b) Git repo with Dockerfile, (c) raw Dockerfile paste, (d) `docker-compose.yml`
- **Build pipeline**: clone → build → tag → run → health-check → swap (zero-downtime where possible)
- **Auto subdomain + HTTPS**: Traefik labels do the routing; Let's Encrypt via Traefik's ACME resolver
- **Env vars & secrets**: per-service, encrypted at rest (Fernet)
- **Persistent volumes**: named Docker volumes mounted per service
- **Custom networks**: each project gets its own bridge network
- **Health checks**: HTTP / TCP / cmd, with auto-restart on failure
- **Auto-redeploy on Git push**: webhook receiver
- **One-click templates**: Postgres, MySQL, Redis, MongoDB, Mongo Express, MinIO, n8n, Uptime Kuma
- **Multi-user + RBAC**: owner / admin / member, with per-project ACL
- **Audit log**: who did what, when
- **System dashboard**: host CPU / RAM / disk / images / networks / volumes
- **CLI** (`dmgr`): mirrors UI for SSH-only workflows

### Nice-to-have (post-MVP, listed for context)
- Multi-server agent (run the manager on one node, agents on others)
- Buildpacks / Nixpacks (auto-detect language, build without Dockerfile)
- Backup & restore for volumes (rclone / restic)
- Preview environments per PR
- Scheduled jobs (cron services)
- Horizontal autoscaling (replicas based on CPU target)
- Slack / Discord / email notifications
- Prometheus exporter + Grafana dashboard

---

## 2. Architecture (one-page mental model)

```
┌──────────────────────────────────────────────────────────────────┐
│  Browser  ──► Traefik ──► UI (React)  ──► API (FastAPI)          │
│                  │                              │                │
│                  ├──► deployed-app-1 (sub.dom.) │                │
│                  └──► deployed-app-N            ▼                │
│                                       Worker (Celery / RQ)       │
│                                              │                   │
│                                              ▼                   │
│                                       Docker engine (socket)     │
│                                              │                   │
│  Postgres  ◄───────────────────────  state (services, users,…)   │
│  Redis     ◄───────────────────────  queue + pub/sub for logs    │
└──────────────────────────────────────────────────────────────────┘
```

**Why these pieces:**
- FastAPI: async, WebSockets for log streaming, OpenAPI for free
- docker-py: official Docker SDK; covers everything the CLI does
- Traefik: dynamic routing via Docker labels = zero-config per service, free Let's Encrypt
- Postgres: services / users / deploys / audit
- Redis: job queue + pub/sub fanout for log streaming to many UI tabs
- Worker process: builds are slow and must not block the API

---

## 3. Folder layout

```
deployment_manager/
├── PLAN.md                  ← this file
├── README.md
├── docker-compose.yml       ← runs the manager itself
├── .env.example
├── pyproject.toml
├── backend/
│   ├── app/
│   │   ├── main.py          ← FastAPI entry
│   │   ├── config.py
│   │   ├── db.py            ← SQLAlchemy / SQLModel
│   │   ├── models/          ← User, Project, Service, Deploy, AuditLog
│   │   ├── api/             ← routers: auth, services, logs, metrics, system
│   │   ├── core/
│   │   │   ├── docker_client.py
│   │   │   ├── builder.py   ← clone + build + tag
│   │   │   ├── runner.py    ← create/start with limits + labels
│   │   │   ├── traefik.py   ← label generators
│   │   │   ├── secrets.py   ← Fernet encrypt/decrypt
│   │   │   └── metrics.py   ← docker stats sampler
│   │   ├── workers/
│   │   │   └── tasks.py     ← Celery / RQ jobs
│   │   └── ws/
│   │       └── logs.py      ← WebSocket log streamer
│   ├── tests/
│   └── alembic/             ← migrations
├── frontend/                ← React + Vite + Tailwind (or HTMX + Jinja)
│   └── src/
├── cli/
│   └── dmgr.py              ← Click-based CLI
├── templates/               ← one-click app YAMLs (postgres.yml, redis.yml…)
└── scripts/
    ├── install.sh           ← one-shot Linux installer
    └── dev.sh
```

---

## 4. The 30-day plan (day-by-day)

> Rule: **end every day with a green commit and a thing you can show.** No "scaffolding" days that produce nothing demoable.

### Week 1 — Foundations (Days 1–7)

**Day 1 (Fri 2026-05-01) — Skeleton & Docker handshake[DONE]**
- `pyproject.toml`, virtualenv, install: `fastapi`, `uvicorn`, `docker`, `pydantic-settings`, `sqlmodel`, `python-jose`, `passlib`, `cryptography`, `httpx`, `rich`.
- `backend/app/main.py`: FastAPI with `/healthz`.
- `backend/app/core/docker_client.py`: `from_env()`, `ping()` — verify it talks to the local daemon.
- Endpoint `GET /api/system/info` returns `client.info()` (engine version, containers, images).
- **Deliverable:** `curl localhost:8000/api/system/info` returns Docker engine info.

**Day 2 — Container listing & inspect[DONE]**
- `GET /api/containers` → list all (running + stopped) with id, name, image, status, ports.
- `GET /api/containers/{id}` → full inspect.
- `GET /api/images`, `GET /api/volumes`, `GET /api/networks`.
- **Deliverable:** every `docker ps`, `docker images`, `docker volume ls`, `docker network ls` is mirrored over HTTP.

**Day 3 — Lifecycle actions (the start/stop/restart/rm/rmi piece) [DONE]**
- `POST /api/containers/{id}/start | stop | restart | kill | pause | unpause`.
- `DELETE /api/containers/{id}?force=&volumes=`.
- `DELETE /api/images/{id}?force=`.
- `POST /api/system/prune` (containers, images, volumes, builder).
- Wire each to docker-py and return the new state.
- **Deliverable:** UI-less but the entire control plane works via curl.

**Day 4 — Database & migrations [DONE]**
- Postgres in `docker-compose.yml` for the manager itself.
- SQLModel models: `User`, `Project`, `Service`, `Deploy`, `EnvVar`, `Secret`, `AuditLog`.
- Alembic init + first migration.
- **Deliverable:** `alembic upgrade head` builds the schema; smoke test by inserting a user.

**Day 5 — Auth [DONE]**
- `/api/auth/register` (first user becomes owner; subsequent require invite).
- `/api/auth/login` → JWT access + refresh.
- FastAPI `Depends(current_user)` on protected routes.
- Bootstrap admin via env vars on first run.
- **Deliverable:** login from curl, protected endpoint rejects without token.

**Day 6 — Run a container with resource limits (the heart of the project) [DONE]**
- `POST /api/services` body: `{name, image, cpus, memory_mb, disk_mb, env, ports, volumes, network, restart_policy}`.
- `core/runner.py` translates that to `client.containers.run(...)` with: `nano_cpus`, `mem_limit`, `pids_limit`, `restart_policy`, `labels`, `network`, `volumes`, `environment`.
- Persist a `Service` row + `Deploy` row tagged `running`.
- **Deliverable:** create a service from JSON, see the container show up in `docker ps` with the limits applied (`docker inspect` confirms).

**Day 7 — Live logs over WebSocket [DONE]**
- `WS /api/services/{id}/logs?tail=200&follow=true`.
- Use `container.logs(stream=True, follow=True)` in a thread, push lines into the WS.
- Handle disconnect, backpressure, ANSI colors passthrough.
- **Deliverable:** open the WS in `wscat`, see logs stream in real time. Ship Week 1.

### Week 2 — Real builds & real metrics (Days 8–14)

**Day 8 — Git → image builder [DONE]**
- `POST /api/services/{id}/deploy` body: `{git_url, branch, commit, dockerfile_path, build_args}`.
- Worker (RQ — simpler than Celery for solo work): clone shallow → `client.images.build(path=…, tag=…)` → stream build logs to Redis pub/sub.
- live check try to access the git url if can access the url its find and show green border if not then red border with message
- Tag images `dmgr/{service}:{short_sha}`.
- **Deliverable:** point at a public repo with a Dockerfile, watch it build, get an image.

**Day 9 — Zero-downtime deploy [DONE]**
- After build: start new container on the same network, wait for health check, swap Traefik label, then stop old.
- Keep the previous image for one rollback.
- `POST /api/services/{id}/rollback` reverts.
- **Deliverable:** redeploy a running service without dropping the existing connection (test with `hey -z 30s`).

**Day 10 — Traefik integration [DONE]**
- Add Traefik to `docker-compose.yml` with ACME (Let's Encrypt) + Docker provider.
- `core/traefik.py` generates labels: `traefik.enable=true`, host rule, port, TLS resolver, middlewares.
- New service flag `domain` → wires the labels automatically.
- For local dev: use `*.localhost` with self-signed.
- **Deliverable:** create a service with `domain=hello.example.com`, hit `https://hello.example.com`, get a real cert.

**Day 11 — Env vars & secrets [DONE]**
- `POST/GET/PUT/DELETE /api/services/{id}/env`.
- Encrypt secret values with Fernet (key from `.env`).
- Redeploy service when env changes (or expose `apply` button).
- **Deliverable:** secret values never appear in DB cleartext; `docker inspect` shows them at runtime.

**Day 12 — Metrics sampler [DONE]**
- `core/metrics.py`: per-service goroutine-style task using `container.stats(stream=True)`, parse CPU% (the canonical formula), mem usage, net rx/tx, blk read/write.
- Push samples to Redis with 60-sample ring buffer per service.
- `GET /api/services/{id}/metrics?range=5m` and `WS /api/services/{id}/metrics` for live.
- **Deliverable:** API returns a time series usable by a chart.

**Day 13 — Health checks & auto-restart [DONE]**
- Add `healthcheck` block to container create call (HTTP / TCP / cmd).
- Subscribe to Docker events (`client.events()`) — on `health_status: unhealthy` or `die` with non-zero exit, follow restart policy and emit an audit event.
- **Deliverable:** kill a container's process, watch it come back; intentionally break health, watch it stop after N retries.

**Day 14 — Volumes & networks UI-ready API [DONE]**
- `POST /api/volumes`, `DELETE /api/volumes/{name}`, list with size.
- `POST /api/networks`, `DELETE /api/networks/{name}`.
- Service create/edit accepts named volumes & networks.
- **Deliverable:** end of week 2 — full backend feature parity with `docker run` for resource-limited services.

### Week 3 — UI & UX (Days 15–21)

**Day 15 — Frontend bootstrap [DONE]**
- `frontend/`: Vite + React + TypeScript + Tailwind + shadcn/ui + TanStack Query + Zustand.
- Login + protected layout + sidebar (Projects, Services, Volumes, Networks, Settings).
- API client generated from FastAPI's OpenAPI spec (`openapi-typescript-codegen`).
- **Deliverable:** log in via the UI.

**Day 16 — Services dashboard [DONE]**
- Table: name, status pill, image, CPU%, RAM%, uptime, actions menu (start / stop / restart / redeploy / delete).
- Status colors driven by container state.
- Filters & search.
- **Deliverable:** create a service from a modal, see it in the table, take actions.

**Day 17 — Service detail page [DONE]**
- Tabs: **Overview**, **Logs**, **Metrics**, **Env**, **Volumes**, **Settings**, **Deploys**.
- Overview: status, image, ports, domain link, last deploy, recent events.
- **Deliverable:** click a row, get a useful detail page.

**Day 18 — Live logs UI**
- WebSocket consumer with auto-scroll, pause-on-hover, search box, level filter (if JSON logs).
- Download last N lines as `.log`.
- **Deliverable:** logs feel as fast and clean as `docker logs -f`.

**Day 19 — Metrics charts**
- Recharts (or uPlot for big ranges): CPU, RAM, network, disk I/O, 4 small sparklines on the table + full charts on detail.
- Range selector: 5m / 1h / 24h.
- **Deliverable:** charts update live; refresh doesn't lose state.

**Day 20 — Create / edit service flow**
- Multi-step form: source (image / git / compose) → resources (CPU sliders, memory, disk) → networking (domain, ports) → env / secrets → review.
- Validation client + server side.
- **Deliverable:** full create flow from UI; redeploy from UI.

**Day 21 — System page + audit log**
- Host info card (cores, RAM, disk, engine version), images / volumes / networks tables with prune buttons.
- Audit log timeline (who did what, when, on which resource).
- **Deliverable:** end of week 3 — UI is usable end-to-end. Soft launch: deploy your own side project to it.

### Week 4 — Productize (Days 22–30)

**Day 22 — Webhooks (auto-deploy on push)**
- `/api/webhooks/{service_token}` accepts GitHub / GitLab / Gitea payloads, verifies HMAC, queues redeploy.
- Show a per-service webhook URL + secret in Settings.
- **Deliverable:** push to GitHub, service redeploys.

**Day 23 — One-click templates**
- `templates/*.yml` (Postgres, Redis, MySQL, MongoDB, MinIO, n8n, Uptime Kuma, Mongo Express, pgAdmin, Mailhog).
- Template = pre-filled service form (image, env defaults, volumes, healthcheck).
- **Deliverable:** "Add Postgres" → 2 clicks → running with persistent volume + auto-generated password (stored as secret).

**Day 24 — `docker-compose.yml` import**
- Parse compose, create one Service per top-level service, wire networks + volumes, deploy as a unit.
- Honor `deploy.resources.limits.cpus / memory`.
- **Deliverable:** paste a compose file, get a running stack.

**Day 25 — RBAC + invites**
- Roles: owner / admin / member / viewer; per-project ACL.
- Invite by email link (token-based; SMTP config optional, otherwise show the link).
- **Deliverable:** invite a teammate, they can deploy in their project but not yours.

**Day 26 — CLI (`dmgr`)**
- Click-based: `dmgr login`, `dmgr ps`, `dmgr logs <svc>`, `dmgr deploy <svc>`, `dmgr exec <svc> -- bash`, `dmgr restart <svc>`.
- Talks to the same API; stores JWT in `~/.dmgr/config.toml`.
- **Deliverable:** publish to PyPI as `pip install dmgr-cli` (or just a wheel).

**Day 27 — Installer & packaging**
- `scripts/install.sh`: detects distro, installs Docker if missing, generates `.env` (random JWT secret, Fernet key, Postgres password), runs `docker compose up -d`, prints the bootstrap admin URL + token.
- Tested on Ubuntu 24.04 + Debian 12.
- **Deliverable:** `curl -fsSL .../install.sh | sudo bash` brings up a working instance.

**Day 28 — Tests & CI**
- `pytest` suite: auth, lifecycle (uses a real Docker daemon in the CI runner via `docker:dind`), builder (cached test image), webhooks (HMAC).
- Frontend: Playwright happy path (login → create service → see logs).
- GitHub Actions: lint (ruff, mypy), test, build images, push to GHCR.
- **Deliverable:** green CI badge.

**Day 29 — Hardening & docs**
- Rate limit auth & webhooks (slowapi).
- Drop dangerous defaults: no privileged, no host network unless explicit toggle.
- Docker socket: prefer mounting `tcp://docker-socket-proxy` (Tecnativa) instead of raw `/var/run/docker.sock`.
- README with screenshots + 5-minute quickstart + architecture diagram.
- **Deliverable:** repo looks like an open-source project a stranger would try.

**Day 30 — Demo & buffer**
- Buffer day for whatever slipped (something always slips).
- Record a 3-minute demo video: install → deploy a Git repo → show logs / metrics → redeploy on push → take it down.
- Tag `v0.1.0`, write a release post.
- **Deliverable:** shippable v0.1.0. Done.

---

## 5. Daily ritual (so you actually finish)

1. Pick the day's task from this file.
2. Make a branch `day-NN-<slug>`.
3. Write the smallest test that proves "deliverable" works.
4. Implement until the test passes.
5. Squash-merge to main, tag the day in the commit (`day-12: metrics sampler`).
6. Update `CHANGELOG.md` with one bullet.
7. If you slip, **delete a nice-to-have** rather than push the deadline.

---

## 6. Risk register (where this usually goes wrong)

| Risk | Mitigation |
|---|---|
| Docker socket = root on host | Use docker-socket-proxy from day 1; document it |
| Build job blocks API | Use RQ worker from day 8; never `docker build` in the request thread |
| Logs WebSocket leaks threads | One `asyncio.Task` per WS, cancel on disconnect, unit-test cleanup |
| Let's Encrypt rate limit during testing | Use Let's Encrypt **staging** resolver until day 30 |
| Frontend over-scoping | If running short, drop React for HTMX + Jinja — same features in half the time |
| Disk-quota limits on Linux | Real per-container disk limits need overlay2 + xfs project quotas; document the constraint, ship soft enforcement (alert + stop) for v0.1 |
| Multi-arch images | Pin `linux/amd64` for v0.1; multi-arch is post-MVP |

---

## 7. What "done" looks like on day 30

- One command brings up the manager on a fresh Ubuntu VPS.
- Open the UI, log in, paste a Git URL, set 0.5 CPU and 512 MB RAM, click deploy.
- Two minutes later the app is on `https://hello.yourdomain.com` with a real cert.
- Push a commit; the UI shows a new deploy land.
- View logs, see metrics, restart, roll back, and finally delete — all from the UI.
- A teammate logs in, deploys their own service, and can't touch yours.

That's v0.1. Everything past that — buildpacks, multi-server, autoscaling, backups — is a v0.2 conversation.
