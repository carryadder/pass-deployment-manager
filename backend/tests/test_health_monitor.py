from types import SimpleNamespace
from uuid import uuid4

from backend.app.core.health_monitor import process_container_event
from backend.app.models.service import Service


def test_unhealthy_event_requests_restart(monkeypatch) -> None:
    service = Service(
        id=uuid4(),
        name="Demo",
        slug="demo-service",
        image="nginx:latest",
        status="running",
        project_id=uuid4(),
        config={"restart_policy": "unless-stopped"},
    )
    restarted = []
    updated = []
    audits = []

    monkeypatch.setattr("backend.app.core.health_monitor._get_service_by_slug", lambda slug: service)
    monkeypatch.setattr(
        "backend.app.core.health_monitor.get_service_container_by_slug",
        lambda slug: SimpleNamespace(id="container-123", restart=lambda timeout=10: restarted.append(timeout)),
    )
    monkeypatch.setattr(
        "backend.app.core.health_monitor._update_service_state",
        lambda service_id, status, extra_config=None: updated.append((status, extra_config)),
    )
    monkeypatch.setattr(
        "backend.app.core.health_monitor._record_audit",
        lambda action, service, details, actor_id=None: audits.append((action, details)),
    )

    process_container_event(
        {
            "Type": "container",
            "status": "health_status: unhealthy",
            "id": "container-123",
            "Actor": {"Attributes": {"dmgr.service.slug": "demo-service"}},
        }
    )

    assert restarted == [10]
    assert updated[0][0] == "unhealthy"
    assert audits[0][0] == "service.health.unhealthy"
    assert audits[1][0] == "service.health.restart_requested"


def test_die_event_with_non_zero_exit_requests_restart(monkeypatch) -> None:
    service = Service(
        id=uuid4(),
        name="Demo",
        slug="demo-service",
        image="nginx:latest",
        status="running",
        project_id=uuid4(),
        config={"restart_policy": "always"},
    )
    started = []
    updated = []

    monkeypatch.setattr("backend.app.core.health_monitor._get_service_by_slug", lambda slug: service)
    monkeypatch.setattr(
        "backend.app.core.health_monitor.get_service_container_by_slug",
        lambda slug: SimpleNamespace(id="container-123", start=lambda: started.append(True)),
    )
    monkeypatch.setattr(
        "backend.app.core.health_monitor._update_service_state",
        lambda service_id, status, extra_config=None: updated.append((status, extra_config)),
    )
    monkeypatch.setattr("backend.app.core.health_monitor._record_audit", lambda *args, **kwargs: None)

    process_container_event(
        {
            "Type": "container",
            "status": "die",
            "id": "container-123",
            "Actor": {"Attributes": {"dmgr.service.slug": "demo-service", "exitCode": "137"}},
        }
    )

    assert started == [True]
    assert updated[0][0] == "crashed"


def test_die_event_with_zero_exit_marks_stopped(monkeypatch) -> None:
    service = Service(
        id=uuid4(),
        name="Demo",
        slug="demo-service",
        image="nginx:latest",
        status="running",
        project_id=uuid4(),
        config={"restart_policy": "unless-stopped"},
    )
    updated = []

    monkeypatch.setattr("backend.app.core.health_monitor._get_service_by_slug", lambda slug: service)
    monkeypatch.setattr(
        "backend.app.core.health_monitor._update_service_state",
        lambda service_id, status, extra_config=None: updated.append((status, extra_config)),
    )

    process_container_event(
        {
            "Type": "container",
            "status": "die",
            "id": "container-123",
            "Actor": {"Attributes": {"dmgr.service.slug": "demo-service", "exitCode": "0"}},
        }
    )

    assert updated[0][0] == "stopped"
