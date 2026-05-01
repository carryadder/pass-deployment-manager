"""One-click service templates.

Each template is a pre-filled service config: image, ports, env defaults,
volumes, healthcheck, and resource defaults. Env entries marked with
`auto_secret=True` are auto-generated as Fernet-encrypted secrets at deploy
time so the user never sees or types the password.

For v0.1 templates live as Python dicts so they participate in type-checking
and don't add a YAML dependency. A future version can load `.yml` files from
this directory if community contributions become a thing.
"""

from __future__ import annotations

from typing import Any

TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "postgres",
        "name": "PostgreSQL",
        "description": "ACID-compliant relational database. Defaults to the postgres user with an auto-generated password and a persistent volume mounted at /var/lib/postgresql/data.",
        "category": "database",
        "icon": "database",
        "image": "postgres:16-alpine",
        "default_resources": {"cpus": 0.5, "memory_mb": 512},
        "ports": [{"container_port": 5432}],
        "volumes": [{"source": "{slug}-data", "target": "/var/lib/postgresql/data", "mode": "rw"}],
        "env": [
            {"key": "POSTGRES_USER", "value": "postgres", "description": "Bootstrap database user."},
            {"key": "POSTGRES_DB", "value": "postgres", "description": "Database created on first boot."},
            {"key": "POSTGRES_PASSWORD", "auto_secret": True, "description": "Generated and stored as a Fernet-encrypted secret."},
        ],
        "healthcheck": {
            "type": "cmd",
            "value": "pg_isready -U postgres",
            "interval_seconds": 10,
            "timeout_seconds": 5,
            "retries": 5,
            "start_period_seconds": 10,
        },
        "restart_policy": "unless-stopped",
        "pids_limit": 256,
    },
    {
        "id": "mysql",
        "name": "MySQL",
        "description": "Popular relational database with persistent storage at /var/lib/mysql.",
        "category": "database",
        "icon": "database",
        "image": "mysql:8",
        "default_resources": {"cpus": 0.5, "memory_mb": 768},
        "ports": [{"container_port": 3306}],
        "volumes": [{"source": "{slug}-data", "target": "/var/lib/mysql", "mode": "rw"}],
        "env": [
            {"key": "MYSQL_DATABASE", "value": "app", "description": "Database created on first boot."},
            {"key": "MYSQL_USER", "value": "app", "description": "Application user."},
            {"key": "MYSQL_PASSWORD", "auto_secret": True, "description": "Application user password (encrypted secret)."},
            {"key": "MYSQL_ROOT_PASSWORD", "auto_secret": True, "description": "Root password (encrypted secret)."},
        ],
        "healthcheck": {
            "type": "cmd",
            "value": "mysqladmin ping -h 127.0.0.1",
            "interval_seconds": 10,
            "timeout_seconds": 5,
            "retries": 5,
            "start_period_seconds": 20,
        },
        "restart_policy": "unless-stopped",
        "pids_limit": 256,
    },
    {
        "id": "redis",
        "name": "Redis",
        "description": "In-memory key/value store. Append-only persistence enabled by default.",
        "category": "database",
        "icon": "zap",
        "image": "redis:7-alpine",
        "default_resources": {"cpus": 0.25, "memory_mb": 256},
        "ports": [{"container_port": 6379}],
        "volumes": [{"source": "{slug}-data", "target": "/data", "mode": "rw"}],
        "command": "redis-server --appendonly yes",
        "env": [],
        "healthcheck": {
            "type": "cmd",
            "value": "redis-cli ping | grep PONG",
            "interval_seconds": 10,
            "timeout_seconds": 3,
            "retries": 5,
        },
        "restart_policy": "unless-stopped",
        "pids_limit": 128,
    },
    {
        "id": "mongo",
        "name": "MongoDB",
        "description": "Document database with root credentials initialised on first boot.",
        "category": "database",
        "icon": "database",
        "image": "mongo:7",
        "default_resources": {"cpus": 0.5, "memory_mb": 768},
        "ports": [{"container_port": 27017}],
        "volumes": [{"source": "{slug}-data", "target": "/data/db", "mode": "rw"}],
        "env": [
            {"key": "MONGO_INITDB_ROOT_USERNAME", "value": "root", "description": "Bootstrap root user."},
            {"key": "MONGO_INITDB_ROOT_PASSWORD", "auto_secret": True, "description": "Generated root password (encrypted secret)."},
        ],
        "healthcheck": {
            "type": "cmd",
            "value": "mongosh --eval 'db.runCommand({ ping: 1 })' --quiet",
            "interval_seconds": 15,
            "timeout_seconds": 5,
            "retries": 5,
            "start_period_seconds": 25,
        },
        "restart_policy": "unless-stopped",
        "pids_limit": 256,
    },
    {
        "id": "minio",
        "name": "MinIO",
        "description": "S3-compatible object storage with built-in console on the second port.",
        "category": "storage",
        "icon": "hard-drive",
        "image": "minio/minio:latest",
        "default_resources": {"cpus": 0.5, "memory_mb": 512},
        "ports": [
            {"container_port": 9000},
            {"container_port": 9001},
        ],
        "volumes": [{"source": "{slug}-data", "target": "/data", "mode": "rw"}],
        "command": "server /data --console-address :9001",
        "env": [
            {"key": "MINIO_ROOT_USER", "value": "admin", "description": "Console user."},
            {"key": "MINIO_ROOT_PASSWORD", "auto_secret": True, "description": "Console password (encrypted secret)."},
        ],
        "healthcheck": {
            "type": "http",
            "value": "http://localhost:9000/minio/health/live",
            "interval_seconds": 15,
            "timeout_seconds": 5,
            "retries": 5,
            "start_period_seconds": 15,
        },
        "restart_policy": "unless-stopped",
        "pids_limit": 256,
    },
    {
        "id": "n8n",
        "name": "n8n",
        "description": "Workflow automation tool with persistent data and an auto-generated encryption key.",
        "category": "automation",
        "icon": "workflow",
        "image": "n8nio/n8n:latest",
        "default_resources": {"cpus": 0.5, "memory_mb": 512},
        "ports": [{"container_port": 5678}],
        "volumes": [{"source": "{slug}-data", "target": "/home/node/.n8n", "mode": "rw"}],
        "env": [
            {"key": "N8N_HOST", "value": "0.0.0.0", "description": "Bind interface."},
            {"key": "N8N_PROTOCOL", "value": "http", "description": "Set to https when fronted by Traefik."},
            {"key": "N8N_ENCRYPTION_KEY", "auto_secret": True, "description": "Encrypts credential payloads (encrypted secret)."},
        ],
        "healthcheck": {
            "type": "http",
            "value": "http://localhost:5678/healthz",
            "interval_seconds": 20,
            "timeout_seconds": 5,
            "retries": 5,
            "start_period_seconds": 20,
        },
        "restart_policy": "unless-stopped",
        "pids_limit": 256,
    },
    {
        "id": "uptime-kuma",
        "name": "Uptime Kuma",
        "description": "Self-hosted uptime monitor with persistent data.",
        "category": "monitoring",
        "icon": "activity",
        "image": "louislam/uptime-kuma:1",
        "default_resources": {"cpus": 0.25, "memory_mb": 256},
        "ports": [{"container_port": 3001}],
        "volumes": [{"source": "{slug}-data", "target": "/app/data", "mode": "rw"}],
        "env": [],
        "healthcheck": {
            "type": "http",
            "value": "http://localhost:3001",
            "interval_seconds": 30,
            "timeout_seconds": 5,
            "retries": 5,
            "start_period_seconds": 20,
        },
        "restart_policy": "unless-stopped",
        "pids_limit": 256,
    },
    {
        "id": "mongo-express",
        "name": "Mongo Express",
        "description": "Web UI for MongoDB. Point ME_CONFIG_MONGODB_URL at your Mongo service.",
        "category": "tooling",
        "icon": "layers",
        "image": "mongo-express:latest",
        "default_resources": {"cpus": 0.25, "memory_mb": 256},
        "ports": [{"container_port": 8081}],
        "volumes": [],
        "env": [
            {"key": "ME_CONFIG_MONGODB_URL", "value": "mongodb://root:CHANGEME@mongo:27017/", "description": "Connection string. Replace CHANGEME with your Mongo root password."},
            {"key": "ME_CONFIG_BASICAUTH_USERNAME", "value": "admin", "description": "Basic auth user."},
            {"key": "ME_CONFIG_BASICAUTH_PASSWORD", "auto_secret": True, "description": "Basic auth password (encrypted secret)."},
        ],
        "healthcheck": None,
        "restart_policy": "unless-stopped",
        "pids_limit": 128,
    },
    {
        "id": "pgadmin",
        "name": "pgAdmin",
        "description": "Web UI for PostgreSQL. Defaults to admin@example.com with an auto-generated password.",
        "category": "tooling",
        "icon": "layers",
        "image": "dpage/pgadmin4:latest",
        "default_resources": {"cpus": 0.25, "memory_mb": 384},
        "ports": [{"container_port": 80}],
        "volumes": [{"source": "{slug}-data", "target": "/var/lib/pgadmin", "mode": "rw"}],
        "env": [
            {"key": "PGADMIN_DEFAULT_EMAIL", "value": "admin@example.com", "description": "Login email."},
            {"key": "PGADMIN_DEFAULT_PASSWORD", "auto_secret": True, "description": "Login password (encrypted secret)."},
        ],
        "healthcheck": None,
        "restart_policy": "unless-stopped",
        "pids_limit": 128,
    },
    {
        "id": "mailhog",
        "name": "MailHog",
        "description": "Capture-only SMTP server with a web inbox at port 8025. Useful for staging email flows.",
        "category": "tooling",
        "icon": "mail",
        "image": "mailhog/mailhog:latest",
        "default_resources": {"cpus": 0.1, "memory_mb": 128},
        "ports": [
            {"container_port": 1025},
            {"container_port": 8025},
        ],
        "volumes": [],
        "env": [],
        "healthcheck": None,
        "restart_policy": "unless-stopped",
        "pids_limit": 64,
    },
]


def list_templates() -> list[dict[str, Any]]:
    return [summarize_template(template) for template in TEMPLATES]


def get_template(template_id: str) -> dict[str, Any] | None:
    for template in TEMPLATES:
        if template["id"] == template_id:
            return template
    return None


def summarize_template(template: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": template["id"],
        "name": template["name"],
        "description": template["description"],
        "category": template["category"],
        "icon": template["icon"],
        "image": template["image"],
        "default_resources": template["default_resources"],
        "ports": template.get("ports", []),
        "volumes": template.get("volumes", []),
        "env": [
            {
                "key": env["key"],
                "value": env.get("value"),
                "auto_secret": bool(env.get("auto_secret")),
                "description": env.get("description"),
            }
            for env in template.get("env", [])
        ],
        "healthcheck": template.get("healthcheck"),
        "restart_policy": template.get("restart_policy", "unless-stopped"),
        "pids_limit": template.get("pids_limit"),
    }


__all__ = ["TEMPLATES", "get_template", "list_templates", "summarize_template"]
