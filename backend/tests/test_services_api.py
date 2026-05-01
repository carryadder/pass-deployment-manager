from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.api.auth import get_current_user
from backend.app.db import get_session
from backend.app.main import app
from backend.app.models.user import User

client = TestClient(app)


class FakeQuery:
    def __init__(self, result):
        self._result = result

    def first(self):
        return self._result


class FakeSession:
    def __init__(self):
        self.added = []
        self.project = None
        self.committed = False

    def exec(self, _statement):
        return FakeQuery(self.project)

    def add(self, item):
        self.added.append(item)
        if item.__class__.__name__ == "Project":
            self.project = item

    def commit(self):
        self.committed = True

    def refresh(self, _item):
        return None

    def rollback(self):
        return None


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
    fake_session = FakeSession()
    current_user = User(
        id=uuid4(),
        email="owner@example.com",
        password_hash="hashed",
        full_name="Owner User",
        is_active=True,
        is_owner=True,
    )

    app.dependency_overrides[get_session] = lambda: fake_session
    app.dependency_overrides[get_current_user] = lambda: current_user
    monkeypatch.setattr(
        "backend.app.api.services.run_service",
        lambda payload: {"Id": "container-123", "Name": "/demo-service"},
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
            "restart_policy": "unless-stopped",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["status"] == "running"
    assert response.json()["container_id"] == "container-123"
    assert fake_session.committed is True
    assert len(fake_session.added) == 3
