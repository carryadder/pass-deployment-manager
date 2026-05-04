from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.api.auth import get_current_user
from backend.app.main import app
from backend.app.models.user import User

client = TestClient(app)


def test_preview_compose_repo_reads_yaml_from_cloned_repo(tmp_path, monkeypatch) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "docker-compose.yml").write_text(
        "services:\n  web:\n    image: nginx:latest\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "backend.app.api.compose.clone_repository",
        lambda git_url, branch=None, commit=None: repo_path,
    )
    monkeypatch.setattr("backend.app.api.compose.cleanup_repository", lambda path: None)

    response = client.post(
        "/api/compose/preview-repo",
        json={
            "git_url": "https://github.com/example/repo.git",
            "name_prefix": "demo",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["compose_path"] == "docker-compose.yml"
    assert payload["services"][0]["name"] == "demo-web"


def test_import_compose_repo_creates_services_from_cloned_repo(tmp_path, monkeypatch) -> None:
    current_user = User(
        id=uuid4(),
        email="owner@example.com",
        password_hash="hashed",
        full_name="Owner User",
        is_active=True,
        is_owner=True,
    )
    app.dependency_overrides[get_current_user] = lambda: current_user

    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "compose.yaml").write_text(
        "services:\n  web:\n    image: nginx:latest\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "backend.app.api.compose.clone_repository",
        lambda git_url, branch=None, commit=None: repo_path,
    )
    monkeypatch.setattr("backend.app.api.compose.cleanup_repository", lambda path: None)
    monkeypatch.setattr(
        "backend.app.api.compose._create_service_sync",
        lambda payload, user: type(
            "CreateResponse",
            (),
            {
                "service_id": uuid4(),
                "deploy_id": uuid4(),
                "status": "running",
                "image": payload.image,
            },
        )(),
    )

    response = client.post(
        "/api/compose/import-repo",
        json={
            "git_url": "https://github.com/example/repo.git",
            "name_prefix": "demo",
        },
    )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    payload = response.json()
    assert payload["compose_path"] == "compose.yaml"
    assert payload["imported"][0]["service_name"] == "demo-web"


def test_preview_compose_repo_supports_build_directive(tmp_path, monkeypatch) -> None:
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "docker-compose.yml").write_text(
        "services:\n  backend:\n    build:\n      context: ./backend\n      dockerfile: Dockerfile\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "backend.app.api.compose.clone_repository",
        lambda git_url, branch=None, commit=None: repo_path,
    )
    monkeypatch.setattr("backend.app.api.compose.cleanup_repository", lambda path: None)

    response = client.post(
        "/api/compose/preview-repo",
        json={"git_url": "https://github.com/example/repo.git"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["services"][0]["image"] == "build:./backend"


def test_import_compose_repo_queues_build_service_from_repo(tmp_path, monkeypatch) -> None:
    current_user = User(
        id=uuid4(),
        email="owner@example.com",
        password_hash="hashed",
        full_name="Owner User",
        is_active=True,
        is_owner=True,
    )
    app.dependency_overrides[get_current_user] = lambda: current_user

    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "docker-compose.yml").write_text(
        "services:\n  backend:\n    build:\n      context: ./backend\n      dockerfile: Dockerfile\n",
        encoding="utf-8",
    )
    queued: dict[str, object] = {}
    monkeypatch.setattr(
        "backend.app.api.compose.clone_repository",
        lambda git_url, branch=None, commit=None: repo_path,
    )
    monkeypatch.setattr("backend.app.api.compose.cleanup_repository", lambda path: None)
    monkeypatch.setattr(
        "backend.app.api.compose.enqueue_deploy_job",
        lambda **kwargs: queued.update(kwargs),
    )

    response = client.post(
        "/api/compose/import-repo",
        json={"git_url": "https://github.com/example/repo.git"},
    )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    payload = response.json()
    assert payload["imported"][0]["service_name"] == "backend"
    assert payload["imported"][0]["status"] == "build_queued"
    assert queued["build_context_path"] == "./backend"
    assert queued["dockerfile_path"] == "Dockerfile"
