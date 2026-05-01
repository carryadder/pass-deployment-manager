from docker.errors import APIError, NotFound
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_start_container_returns_updated_state(monkeypatch) -> None:
    expected = {"Id": "abc123", "State": {"Status": "running"}}

    monkeypatch.setattr("backend.app.api.lifecycle.start_container", lambda _: expected)

    response = client.post("/api/containers/abc123/start")

    assert response.status_code == 200
    assert response.json() == expected


def test_delete_container_passes_query_flags(monkeypatch) -> None:
    observed: dict = {}

    def fake_remove(container_id: str, force: bool, volumes: bool) -> dict:
        observed.update({"container_id": container_id, "force": force, "volumes": volumes})
        return {"deleted": True, "id": container_id}

    monkeypatch.setattr("backend.app.api.lifecycle.remove_container", fake_remove)

    response = client.delete("/api/containers/abc123?force=true&volumes=true")

    assert response.status_code == 200
    assert response.json() == {"deleted": True, "id": "abc123"}
    assert observed == {"container_id": "abc123", "force": True, "volumes": True}


def test_delete_image_returns_deleted_payload(monkeypatch) -> None:
    expected = {
        "deleted": True,
        "id": "sha256:123",
        "short_id": "sha256:123",
        "tags": ["nginx:latest"],
        "force": True,
    }

    monkeypatch.setattr(
        "backend.app.api.lifecycle.remove_image",
        lambda _, force: {**expected, "force": force},
    )

    response = client.delete("/api/images/sha256:123?force=true")

    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert response.json()["force"] is True


def test_prune_system_returns_result(monkeypatch) -> None:
    expected = {
        "containers": {"ContainersDeleted": ["abc123"], "SpaceReclaimed": 100},
        "images": {"ImagesDeleted": ["sha256:123"], "SpaceReclaimed": 200},
        "volumes": {"VolumesDeleted": ["demo-data"], "SpaceReclaimed": 300},
        "builder_cache": {"CachesDeleted": ["cache-1"], "SpaceReclaimed": 400},
    }

    monkeypatch.setattr("backend.app.api.lifecycle.prune_system", lambda: expected)

    response = client.post("/api/system/prune")

    assert response.status_code == 200
    assert response.json() == expected


def test_container_not_found_maps_to_404(monkeypatch) -> None:
    def fake_start(_: str) -> dict:
        raise NotFound("missing")

    monkeypatch.setattr("backend.app.api.lifecycle.start_container", fake_start)

    response = client.post("/api/containers/missing/start")

    assert response.status_code == 404
    assert response.json() == {"detail": "Container not found"}


def test_api_error_maps_to_409(monkeypatch) -> None:
    def fake_pause(_: str) -> dict:
        raise APIError("container cannot be paused")

    monkeypatch.setattr("backend.app.api.lifecycle.pause_container", fake_pause)

    response = client.post("/api/containers/abc123/pause")

    assert response.status_code == 409
    assert "container cannot be paused" in response.json()["detail"]
