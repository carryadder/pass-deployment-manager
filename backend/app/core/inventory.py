from docker.errors import NotFound

from backend.app.core.docker_client import get_docker_client


def _normalize_ports(port_settings: dict | None) -> list[dict]:
    if not port_settings:
        return []

    ports: list[dict] = []
    for container_port, host_bindings in port_settings.items():
        if not host_bindings:
            ports.append(
                {
                    "container_port": container_port,
                    "host_ip": None,
                    "host_port": None,
                }
            )
            continue

        for binding in host_bindings:
            ports.append(
                {
                    "container_port": container_port,
                    "host_ip": binding.get("HostIp"),
                    "host_port": binding.get("HostPort"),
                }
            )
    return ports


def list_containers() -> list[dict]:
    client = get_docker_client()
    containers = client.containers.list(all=True)

    return [
        {
            "id": container.id,
            "name": container.name,
            "image": container.image.tags[0] if container.image.tags else container.image.short_id,
            "status": container.status,
            "state": container.attrs.get("State", {}),
            "ports": _normalize_ports(container.attrs.get("NetworkSettings", {}).get("Ports")),
            "created": container.attrs.get("Created"),
        }
        for container in containers
    ]


def inspect_container(container_id: str) -> dict:
    client = get_docker_client()
    container = client.containers.get(container_id)
    return container.attrs


def list_images() -> list[dict]:
    client = get_docker_client()
    images = client.images.list()

    return [
        {
            "id": image.id,
            "short_id": image.short_id,
            "tags": image.tags,
            "created": image.attrs.get("Created"),
            "size": image.attrs.get("Size"),
            "labels": image.labels,
        }
        for image in images
    ]


def list_volumes() -> list[dict]:
    client = get_docker_client()
    volumes = client.volumes.list()

    return [
        {
            "name": volume.name,
            "driver": volume.attrs.get("Driver"),
            "mountpoint": volume.attrs.get("Mountpoint"),
            "scope": volume.attrs.get("Scope"),
            "labels": volume.attrs.get("Labels") or {},
            "options": volume.attrs.get("Options") or {},
        }
        for volume in volumes
    ]


def list_networks() -> list[dict]:
    client = get_docker_client()
    networks = client.networks.list()

    return [
        {
            "id": network.id,
            "name": network.name,
            "short_id": network.short_id,
            "driver": network.attrs.get("Driver"),
            "scope": network.attrs.get("Scope"),
            "labels": network.attrs.get("Labels") or {},
        }
        for network in networks
    ]


__all__ = [
    "NotFound",
    "inspect_container",
    "list_containers",
    "list_images",
    "list_networks",
    "list_volumes",
]
