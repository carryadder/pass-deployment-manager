from __future__ import annotations

import threading
from typing import Any

from sqlmodel import select

from backend.app.db import session_scope
from backend.app.models.audit_log import AuditLog
from backend.app.models.project import Project
from backend.app.models.service import Service
from backend.app.core.docker_client import get_docker_client
from backend.app.core.runner import get_service_container_by_slug


def _service_restart_policy(service: Service) -> str:
    return str(service.config.get("restart_policy", "unless-stopped"))


def _should_restart(service: Service) -> bool:
    return _service_restart_policy(service) != "no"


def _record_audit(action: str, service: Service, details: dict[str, Any], actor_id=None) -> None:
    with session_scope() as session:
        session.add(
            AuditLog(
                actor_id=actor_id,
                action=action,
                resource_type="service",
                resource_id=str(service.id),
                details=details,
            )
        )
        session.commit()


def _get_service_by_slug(service_slug: str) -> Service | None:
    with session_scope() as session:
        service = session.exec(select(Service).where(Service.slug == service_slug)).first()
        if service is None:
            return None
        project = session.get(Project, service.project_id)
        if project is not None:
            service.project = project
        return service


def _update_service_state(service_id, status: str, extra_config: dict[str, Any] | None = None) -> None:
    with session_scope() as session:
        service = session.get(Service, service_id)
        if service is None:
            return
        config = dict(service.config)
        if extra_config:
            config.update(extra_config)
        service.status = status
        service.config = config
        session.add(service)
        session.commit()


def process_container_event(event: dict[str, Any]) -> None:
    actor = event.get("Actor", {}) or {}
    attributes = actor.get("Attributes", {}) or {}
    service_slug = attributes.get("dmgr.service.slug")
    if not service_slug:
        return

    service = _get_service_by_slug(service_slug)
    if service is None:
        return

    status = str(event.get("status", ""))
    action = str(event.get("Action", ""))
    event_name = status or action

    if event_name == "health_status: unhealthy":
        _update_service_state(service.id, "unhealthy", {"last_health_event": "unhealthy"})
        _record_audit(
            "service.health.unhealthy",
            service,
            {"container_id": event.get("id"), "status": event_name},
        )
        if _should_restart(service):
            container = get_service_container_by_slug(service.slug)
            if container is not None:
                try:
                    container.restart(timeout=10)
                    _record_audit(
                        "service.health.restart_requested",
                        service,
                        {"container_id": container.id, "reason": "unhealthy"},
                    )
                except Exception:
                    pass
        return

    if event_name == "die":
        exit_code = int((attributes.get("exitCode") or 0))
        if exit_code == 0:
            _update_service_state(service.id, "stopped", {"last_exit_code": exit_code})
            return

        _update_service_state(service.id, "crashed", {"last_exit_code": exit_code})
        _record_audit(
            "service.process.died",
            service,
            {"container_id": event.get("id"), "exit_code": exit_code},
        )
        if _should_restart(service):
            container = get_service_container_by_slug(service.slug)
            if container is not None:
                try:
                    container.start()
                    _record_audit(
                        "service.process.restart_requested",
                        service,
                        {"container_id": container.id, "reason": "non_zero_exit", "exit_code": exit_code},
                    )
                except Exception:
                    pass


class HealthMonitor:
    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="health-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._thread = None

    def _run(self) -> None:
        client = get_docker_client()
        try:
            for event in client.events(decode=True):
                if self._stop_event.is_set():
                    break
                if event.get("Type") != "container":
                    continue
                process_container_event(event)
        except Exception:
            return


health_monitor = HealthMonitor()


__all__ = ["HealthMonitor", "health_monitor", "process_container_event"]
