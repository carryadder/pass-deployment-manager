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
