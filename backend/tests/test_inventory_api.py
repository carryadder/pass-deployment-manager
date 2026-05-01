from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_list_containers_returns_payload(monkeypatch) -> None:
    expected = [
        {
            "id": "abc123",
            "name": "demo",
            "image": "nginx:latest",
            "status": "running",
            "state": {"Status": "running"},
            "ports": [{"container_port": "80/tcp", "host_ip": "0.0.0.0", "host_port": "8080"}],
            "created": "2026-05-01T10:00:00Z",
        }
    ]

    monkeypatch.setattr("backend.app.api.inventory.list_containers", lambda: expected)

    response = client.get("/api/containers")

    assert response.status_code == 200
    assert response.json() == expected


def test_get_container_returns_inspect_data(monkeypatch) -> None:
    expected = {"Id": "abc123", "Name": "/demo"}

    monkeypatch.setattr("backend.app.api.inventory.inspect_container", lambda _: expected)

    response = client.get("/api/containers/abc123")

    assert response.status_code == 200
    assert response.json() == expected


def test_list_images_returns_payload(monkeypatch) -> None:
    expected = [
        {
            "id": "sha256:123",
            "short_id": "sha256:123",
            "tags": ["nginx:latest"],
            "created": "2026-05-01T10:00:00Z",
            "size": 123456,
            "labels": {"maintainer": "demo"},
        }
    ]

    monkeypatch.setattr("backend.app.api.inventory.list_images", lambda: expected)

    response = client.get("/api/images")

    assert response.status_code == 200
    assert response.json() == expected


def test_list_volumes_returns_payload(monkeypatch) -> None:
    expected = [
        {
            "name": "demo-data",
            "driver": "local",
            "mountpoint": "/var/lib/docker/volumes/demo-data/_data",
            "scope": "local",
            "labels": {},
            "options": {},
            "size_bytes": 2048,
            "ref_count": 1,
        }
    ]

    monkeypatch.setattr("backend.app.api.inventory.list_volumes", lambda: expected)

    response = client.get("/api/volumes")

    assert response.status_code == 200
    assert response.json() == expected


def test_create_volume_returns_payload(monkeypatch) -> None:
    expected = {
        "name": "demo-data",
        "driver": "local",
        "mountpoint": "/var/lib/docker/volumes/demo-data/_data",
        "scope": "local",
        "labels": {"env": "dev"},
        "options": {"o": "bind"},
        "size_bytes": None,
        "ref_count": None,
    }

    monkeypatch.setattr("backend.app.api.inventory.create_volume", lambda *args: expected)

    response = client.post(
        "/api/volumes",
        json={
            "name": "demo-data",
            "driver": "local",
            "labels": {"env": "dev"},
            "options": {"o": "bind"},
        },
    )

    assert response.status_code == 201
    assert response.json() == expected


def test_delete_volume_returns_payload(monkeypatch) -> None:
    expected = {"name": "demo-data", "deleted": True, "force": True}

    monkeypatch.setattr("backend.app.api.inventory.remove_volume", lambda *args: expected)

    response = client.delete("/api/volumes/demo-data?force=true")

    assert response.status_code == 200
    assert response.json() == expected


def test_list_networks_returns_payload(monkeypatch) -> None:
    expected = [
        {
            "id": "network123",
            "name": "bridge",
            "short_id": "network123",
            "driver": "bridge",
            "scope": "local",
            "labels": {},
            "internal": False,
            "attachable": False,
            "options": {},
            "containers": 2,
        }
    ]

    monkeypatch.setattr("backend.app.api.inventory.list_networks", lambda: expected)

    response = client.get("/api/networks")

    assert response.status_code == 200
    assert response.json() == expected


def test_create_network_returns_payload(monkeypatch) -> None:
    expected = {
        "id": "network123",
        "name": "demo-network",
        "short_id": "network123",
        "driver": "bridge",
        "scope": "local",
        "labels": {"stack": "demo"},
        "internal": False,
        "attachable": True,
        "options": {"com.docker.network.bridge.name": "br-demo"},
        "containers": 0,
    }

    monkeypatch.setattr("backend.app.api.inventory.create_network", lambda *args: expected)

    response = client.post(
        "/api/networks",
        json={
            "name": "demo-network",
            "driver": "bridge",
            "attachable": True,
            "labels": {"stack": "demo"},
            "options": {"com.docker.network.bridge.name": "br-demo"},
        },
    )

    assert response.status_code == 201
    assert response.json() == expected


def test_delete_network_returns_payload(monkeypatch) -> None:
    expected = {"name": "demo-network", "deleted": True}

    monkeypatch.setattr("backend.app.api.inventory.remove_network", lambda _: expected)

    response = client.delete("/api/networks/demo-network")

    assert response.status_code == 200
    assert response.json() == expected
