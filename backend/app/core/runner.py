from __future__ import annotations

import time
from decimal import Decimal

from docker.errors import DockerException, NotFound

from backend.app.core.docker_client import get_docker_client


def _build_healthcheck_config(payload: dict) -> dict | None:
    healthcheck = payload.get("healthcheck")
    if not healthcheck:
        return None

    health_type = healthcheck.get("type")
    value = healthcheck.get("value")
    if not health_type or not value:
        return None

    interval_seconds = int(healthcheck.get("interval_seconds", 10))
    timeout_seconds = int(healthcheck.get("timeout_seconds", 3))
    start_period_seconds = int(healthcheck.get("start_period_seconds", 5))
    retries = int(healthcheck.get("retries", 3))

    if health_type == "http":
        command = f"wget -qO- {value} >/dev/null 2>&1 || exit 1"
        test = ["CMD-SHELL", command]
    elif health_type == "tcp":
        host, port = str(value).rsplit(":", 1)
        command = f"nc -z {host} {port} >/dev/null 2>&1 || exit 1"
        test = ["CMD-SHELL", command]
    elif health_type == "cmd":
        test = ["CMD-SHELL", str(value)]
    else:
        return None

    return {
        "test": test,
        "interval": interval_seconds * 1_000_000_000,
        "timeout": timeout_seconds * 1_000_000_000,
        "start_period": start_period_seconds * 1_000_000_000,
        "retries": retries,
    }


def build_run_config(payload: dict) -> dict:
    ports = {
        str(port["container_port"]): port["host_port"]
        for port in payload.get("ports", [])
        if port.get("host_port") is not None
    }
    exposed_ports = {
        str(port["container_port"]): None
        for port in payload.get("ports", [])
        if port.get("host_port") is None
    }
    volume_bindings = {
        volume["source"]: {"bind": volume["target"], "mode": volume.get("mode", "rw")}
        for volume in payload.get("volumes", [])
    }

    config = {
        "image": payload["image"],
        "name": payload["name"],
        "detach": True,
        "environment": payload.get("env", {}),
        "labels": payload.get("labels", {}),
        "network": payload.get("network"),
        "ports": ports or exposed_ports or None,
        "volumes": volume_bindings or None,
        "restart_policy": {"Name": payload.get("restart_policy", "unless-stopped")},
        "nano_cpus": int(Decimal(str(payload["cpus"])) * Decimal("1000000000")),
        "mem_limit": int(payload["memory_mb"]) * 1024 * 1024,
        "pids_limit": payload.get("pids_limit", 256),
        "healthcheck": _build_healthcheck_config(payload),
    }

    if payload.get("disk_mb") is not None:
        config["storage_opt"] = {"size": f"{payload['disk_mb']}m"}

    return {key: value for key, value in config.items() if value is not None}


def ensure_network_exists(name: str):
    client = get_docker_client()
    networks = client.networks.list(names=[name])
    if networks:
        return networks[0]
    return client.networks.create(name=name, driver="bridge", check_duplicate=True)


def run_service(payload: dict) -> dict:
    client = get_docker_client()
    primary_network = payload.get("network")
    extra_networks = [name for name in payload.get("extra_networks", []) if name and name != primary_network]

    if primary_network:
        ensure_network_exists(primary_network)
    for network_name in extra_networks:
        ensure_network_exists(network_name)

    container = client.containers.run(**build_run_config(payload))
    for network_name in extra_networks:
        client.networks.get(network_name).connect(container)
    container.reload()
    return container.attrs


def get_service_container_by_slug(service_slug: str):
    client = get_docker_client()
    containers = client.containers.list(
        all=True,
        filters={"label": f"dmgr.service.slug={service_slug}"},
    )
    return containers[0] if containers else None


def get_container_by_name(container_name: str):
    client = get_docker_client()
    try:
        return client.containers.get(container_name)
    except NotFound:
        return None


def remove_service_container_by_slug(service_slug: str) -> None:
    container = get_service_container_by_slug(service_slug)
    if container is None:
        return
    container.remove(force=True)


def remove_service_container_by_name(container_name: str) -> None:
    container = get_container_by_name(container_name)
    if container is None:
        return
    container.remove(force=True)


def wait_for_container_ready(container, timeout_seconds: int = 60) -> dict:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        container.reload()
        state = container.attrs.get("State", {})
        health = state.get("Health", {})
        health_status = health.get("Status")

        if state.get("Status") != "running":
            raise DockerException(f"Container exited before becoming ready: {state.get('Status')}")
        if health_status == "healthy":
            return container.attrs
        if health_status is None:
            return container.attrs
        if health_status == "unhealthy":
            raise DockerException("Container reported unhealthy status")
        time.sleep(1)

    raise DockerException("Timed out waiting for container readiness")


def stop_and_remove_container(container) -> None:
    try:
        container.stop(timeout=10)
    finally:
        container.remove(force=True)


__all__ = [
    "DockerException",
    "build_run_config",
    "ensure_network_exists",
    "get_container_by_name",
    "get_service_container_by_slug",
    "remove_service_container_by_name",
    "remove_service_container_by_slug",
    "run_service",
    "stop_and_remove_container",
    "wait_for_container_ready",
]
