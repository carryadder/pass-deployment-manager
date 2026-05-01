from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.api.auth import get_current_user
from backend.app.main import app
from backend.app.models.user import User

client = TestClient(app)


def test_create_service_requires_authentication() -> None:
    response = client.post(
        "/api/services",
        json={
            "name": "demo",
            "image": "nginx:latest",
            "cpus": 0.5,
            "memory_mb": 512,
        },
    )

    assert response.status_code == 401


def test_create_service_persists_service_and_deploy(monkeypatch) -> None:
    current_user = User(
        id=uuid4(),
        email="owner@example.com",
        password_hash="hashed",
        full_name="Owner User",
        is_active=True,
        is_owner=True,
    )

    app.dependency_overrides[get_current_user] = lambda: current_user
    monkeypatch.setattr(
        "backend.app.api.services._create_service_sync",
        lambda payload, user: {
            "service_id": str(uuid4()),
            "deploy_id": str(uuid4()),
            "status": "running",
            "container_id": "container-123",
            "container_name": "/demo-service",
            "image": payload.image,
            "project_id": str(uuid4()),
        },
    )

    response = client.post(
        "/api/services",
        json={
            "name": "Demo Service",
            "image": "nginx:latest",
            "cpus": 0.5,
            "memory_mb": 512,
            "disk_mb": 1024,
            "env": {"APP_ENV": "production"},
            "ports": [{"container_port": 80, "host_port": 8080}],
            "volumes": [{"source": "demo-data", "target": "/data", "mode": "rw"}],
            "network": "demo-network",
            "domain": "demo.localhost",
            "restart_policy": "unless-stopped",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["status"] == "running"
    assert response.json()["container_id"] == "container-123"


def test_deploy_service_from_git_queues_build(monkeypatch) -> None:
    current_user = User(
        id=uuid4(),
        email="owner@example.com",
        password_hash="hashed",
        full_name="Owner User",
        is_active=True,
        is_owner=True,
    )
    app.dependency_overrides[get_current_user] = lambda: current_user
    monkeypatch.setattr(
        "backend.app.api.services._deploy_service_from_git_sync",
        lambda service_id, payload, user: {
            "deploy_id": str(uuid4()),
            "service_id": str(service_id),
            "status": "queued",
            "source_type": "git",
            "source_ref": payload.git_url,
            "image_tag": None,
        },
    )

    service_id = uuid4()
    response = client.post(
        f"/api/services/{service_id}/deploy",
        json={
            "git_url": "https://github.com/example/demo.git",
            "branch": "main",
            "dockerfile_path": "Dockerfile",
            "build_args": {"APP_ENV": "production"},
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert response.json()["service_id"] == str(service_id)
    assert response.json()["source_ref"] == "https://github.com/example/demo.git"


def test_rollout_built_service_queues_rollout(monkeypatch) -> None:
    current_user = User(
        id=uuid4(),
        email="owner@example.com",
        password_hash="hashed",
        full_name="Owner User",
        is_active=True,
        is_owner=True,
    )
    app.dependency_overrides[get_current_user] = lambda: current_user
    monkeypatch.setattr(
        "backend.app.api.services._rollout_built_service_sync",
        lambda service_id, user: {
            "deploy_id": str(uuid4()),
            "service_id": str(service_id),
            "status": "built",
            "source_type": "git",
            "source_ref": "https://github.com/example/demo.git",
            "image_tag": "dmgr/demo-service:abc1234",
        },
    )

    service_id = uuid4()
    response = client.post(f"/api/services/{service_id}/rollout")

    app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["service_id"] == str(service_id)
    assert response.json()["image_tag"] == "dmgr/demo-service:abc1234"


def test_rollback_service_queues_previous_image(monkeypatch) -> None:
    current_user = User(
        id=uuid4(),
        email="owner@example.com",
        password_hash="hashed",
        full_name="Owner User",
        is_active=True,
        is_owner=True,
    )
    app.dependency_overrides[get_current_user] = lambda: current_user
    monkeypatch.setattr(
        "backend.app.api.services._rollback_service_sync",
        lambda service_id, user: {
            "deploy_id": str(uuid4()),
            "status": "queued",
            "image_tag": "dmgr/demo-service:old",
        },
    )

    response = client.post(f"/api/services/{uuid4()}/rollback")

    app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["image_tag"] == "dmgr/demo-service:old"


def test_list_service_env_returns_entries(monkeypatch) -> None:
    current_user = User(
        id=uuid4(),
        email="owner@example.com",
        password_hash="hashed",
        full_name="Owner User",
        is_active=True,
        is_owner=True,
    )
    app.dependency_overrides[get_current_user] = lambda: current_user
    monkeypatch.setattr(
        "backend.app.api.services._list_service_env_sync",
        lambda service_id, user: [
            {"key": "APP_ENV", "value": "production", "is_secret": False, "has_value": True},
            {"key": "API_KEY", "value": None, "is_secret": True, "has_value": True},
        ],
    )

    response = client.get(f"/api/services/{uuid4()}/env")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["key"] == "APP_ENV"
    assert response.json()[1]["is_secret"] is True
    assert response.json()[1]["value"] is None


def test_create_service_env_returns_apply_status(monkeypatch) -> None:
    current_user = User(
        id=uuid4(),
        email="owner@example.com",
        password_hash="hashed",
        full_name="Owner User",
        is_active=True,
        is_owner=True,
    )
    app.dependency_overrides[get_current_user] = lambda: current_user
    monkeypatch.setattr(
        "backend.app.api.services._create_service_env_sync",
        lambda service_id, payload, user: {
            "entry": {
                "key": payload.key,
                "value": None if payload.is_secret else payload.value,
                "is_secret": payload.is_secret,
                "has_value": True,
            },
            "applied": payload.apply,
            "deploy_id": str(uuid4()),
            "service_status": "env_update_queued",
        },
    )

    response = client.post(
        f"/api/services/{uuid4()}/env",
        json={
            "key": "API_KEY",
            "value": "super-secret",
            "is_secret": True,
            "apply": True,
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["entry"]["key"] == "API_KEY"
    assert response.json()["entry"]["is_secret"] is True
    assert response.json()["entry"]["value"] is None
    assert response.json()["applied"] is True


def test_delete_service_env_returns_deleted(monkeypatch) -> None:
    current_user = User(
        id=uuid4(),
        email="owner@example.com",
        password_hash="hashed",
        full_name="Owner User",
        is_active=True,
        is_owner=True,
    )
    app.dependency_overrides[get_current_user] = lambda: current_user
    monkeypatch.setattr(
        "backend.app.api.services._delete_service_env_sync",
        lambda service_id, key, apply, user: {
            "key": key,
            "deleted": True,
            "applied": apply,
            "deploy_id": None,
            "service_status": "running",
        },
    )

    response = client.delete(f"/api/services/{uuid4()}/env/API_KEY?apply=false")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["key"] == "API_KEY"
    assert response.json()["deleted"] is True
    assert response.json()["applied"] is False


def test_read_service_metrics_returns_samples(monkeypatch) -> None:
    current_user = User(
        id=uuid4(),
        email="owner@example.com",
        password_hash="hashed",
        full_name="Owner User",
        is_active=True,
        is_owner=True,
    )
    app.dependency_overrides[get_current_user] = lambda: current_user
    monkeypatch.setattr(
        "backend.app.api.services._read_service_metrics_sync",
        lambda service_id, user, range_value: [
            {
                "timestamp": "2026-05-01T12:00:00+00:00",
                "cpu_percent": 12.5,
                "memory_usage_bytes": 1048576,
                "memory_limit_bytes": 2097152,
                "memory_percent": 50.0,
                "network_rx_bytes": 1200,
                "network_tx_bytes": 800,
                "block_read_bytes": 64,
                "block_write_bytes": 128,
                "pids": 7,
            }
        ],
    )

    response = client.get(f"/api/services/{uuid4()}/metrics?range=5m")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()[0]["cpu_percent"] == 12.5
    assert response.json()[0]["memory_percent"] == 50.0
