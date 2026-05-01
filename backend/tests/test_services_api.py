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


def test_deploy_service_from_git_queues_build(monkeypatch) -> None:
    fake_session = FakeSession()
    current_user = User(
        id=uuid4(),
        email="owner@example.com",
        password_hash="hashed",
        full_name="Owner User",
        is_active=True,
        is_owner=True,
    )

    from backend.app.models.project import Project
    from backend.app.models.service import Service

    project = Project(
        id=uuid4(),
        name="Owner Project",
        slug="owner-project",
        owner_id=current_user.id,
        description=None,
    )
    service = Service(
        id=uuid4(),
        name="Demo Service",
        slug="demo-service",
        image="nginx:latest",
        status="running",
        project_id=project.id,
        config={},
    )
    service.project = project
    fake_session.project = project

    def fake_get(model, object_id):
        if model.__name__ == "Service":
            return service
        return None

    fake_session.get = fake_get

    observed: dict = {}

    app.dependency_overrides[get_session] = lambda: fake_session
    app.dependency_overrides[get_current_user] = lambda: current_user
    monkeypatch.setattr(
        "backend.app.api.services.enqueue_deploy_job",
        lambda **kwargs: observed.update(kwargs),
    )

    response = client.post(
        f"/api/services/{service.id}/deploy",
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
    assert observed["service_id"] == service.id
    assert observed["git_url"] == "https://github.com/example/demo.git"


def test_rollout_built_service_queues_rollout(monkeypatch) -> None:
    fake_session = FakeSession()
    current_user = User(
        id=uuid4(),
        email="owner@example.com",
        password_hash="hashed",
        full_name="Owner User",
        is_active=True,
        is_owner=True,
    )

    from backend.app.models.deploy import Deploy
    from backend.app.models.project import Project
    from backend.app.models.service import Service

    project = Project(
        id=uuid4(),
        name="Owner Project",
        slug="owner-project",
        owner_id=current_user.id,
        description=None,
    )
    service = Service(
        id=uuid4(),
        name="Demo Service",
        slug="demo-service",
        image="nginx:old",
        status="built",
        project_id=project.id,
        config={},
    )
    service.project = project
    deploy = Deploy(
        service_id=service.id,
        status="built",
        source_type="git",
        source_ref="https://github.com/example/demo.git",
        image_tag="dmgr/demo-service:abc1234",
    )

    class DeployQuery:
        def __init__(self, result):
            self.result = result

        def first(self):
            return self.result

    def fake_get(model, object_id):
        if model.__name__ == "Service":
            return service
        return None

    def fake_exec(_statement):
        return DeployQuery(deploy)

    fake_session.get = fake_get
    fake_session.exec = fake_exec

    observed: dict = {}
    app.dependency_overrides[get_session] = lambda: fake_session
    app.dependency_overrides[get_current_user] = lambda: current_user
    monkeypatch.setattr(
        "backend.app.api.services.enqueue_rollout_job",
        lambda deploy_id, service_id, image_tag: observed.update(
            {"deploy_id": deploy_id, "service_id": service_id, "image_tag": image_tag}
        ),
    )

    response = client.post(f"/api/services/{service.id}/rollout")

    app.dependency_overrides.clear()

    assert response.status_code == 202
    assert observed["service_id"] == service.id
    assert observed["image_tag"] == "dmgr/demo-service:abc1234"


def test_rollback_service_queues_previous_image(monkeypatch) -> None:
    fake_session = FakeSession()
    current_user = User(
        id=uuid4(),
        email="owner@example.com",
        password_hash="hashed",
        full_name="Owner User",
        is_active=True,
        is_owner=True,
    )

    from backend.app.models.project import Project
    from backend.app.models.service import Service

    project = Project(
        id=uuid4(),
        name="Owner Project",
        slug="owner-project",
        owner_id=current_user.id,
        description=None,
    )
    service = Service(
        id=uuid4(),
        name="Demo Service",
        slug="demo-service",
        image="dmgr/demo-service:new",
        status="running",
        project_id=project.id,
        config={"previous_image": "dmgr/demo-service:old"},
    )
    service.project = project

    def fake_get(model, object_id):
        if model.__name__ == "Service":
            return service
        return None

    fake_session.get = fake_get

    observed: dict = {}
    app.dependency_overrides[get_session] = lambda: fake_session
    app.dependency_overrides[get_current_user] = lambda: current_user
    monkeypatch.setattr(
        "backend.app.api.services.enqueue_rollout_job",
        lambda deploy_id, service_id, image_tag: observed.update(
            {"deploy_id": deploy_id, "service_id": service_id, "image_tag": image_tag}
        ),
    )

    response = client.post(f"/api/services/{service.id}/rollback")

    app.dependency_overrides.clear()

    assert response.status_code == 202
    assert observed["service_id"] == service.id
    assert observed["image_tag"] == "dmgr/demo-service:old"
