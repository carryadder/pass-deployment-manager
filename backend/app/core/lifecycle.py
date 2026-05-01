from docker.errors import APIError, NotFound

from backend.app.core.docker_client import get_docker_client


def _inspect_container(container_id: str) -> dict:
    client = get_docker_client()
    container = client.containers.get(container_id)
    return container.attrs


def start_container(container_id: str) -> dict:
    client = get_docker_client()
    container = client.containers.get(container_id)
    container.start()
    container.reload()
    return container.attrs


def stop_container(container_id: str) -> dict:
    client = get_docker_client()
    container = client.containers.get(container_id)
    container.stop()
    container.reload()
    return container.attrs


def restart_container(container_id: str) -> dict:
    client = get_docker_client()
    container = client.containers.get(container_id)
    container.restart()
    container.reload()
    return container.attrs


def kill_container(container_id: str) -> dict:
    client = get_docker_client()
    container = client.containers.get(container_id)
    container.kill()
    container.reload()
    return container.attrs


def pause_container(container_id: str) -> dict:
    client = get_docker_client()
    container = client.containers.get(container_id)
    container.pause()
    container.reload()
    return container.attrs


def unpause_container(container_id: str) -> dict:
    client = get_docker_client()
    container = client.containers.get(container_id)
    container.unpause()
    container.reload()
    return container.attrs


def remove_container(container_id: str, force: bool = False, volumes: bool = False) -> dict:
    snapshot = _inspect_container(container_id)
    client = get_docker_client()
    container = client.containers.get(container_id)
    container.remove(force=force, v=volumes)
    return {
        "deleted": True,
        "id": snapshot.get("Id", container_id),
        "name": snapshot.get("Name"),
        "force": force,
        "volumes": volumes,
    }


def remove_image(image_id: str, force: bool = False) -> dict:
    client = get_docker_client()
    image = client.images.get(image_id)
    snapshot = {
        "id": image.id,
        "tags": image.tags,
        "short_id": image.short_id,
    }
    client.images.remove(image=image_id, force=force)
    return {
        "deleted": True,
        "force": force,
        **snapshot,
    }


def prune_system(targets: set[str] | None = None) -> dict:
    client = get_docker_client()
    selected = targets or {"containers", "images", "volumes", "builder"}
    result: dict = {}

    if "containers" in selected:
        result["containers"] = client.containers.prune()
    if "images" in selected:
        result["images"] = client.images.prune()
    if "volumes" in selected:
        result["volumes"] = client.volumes.prune()
    if "builder" in selected:
        if hasattr(client.api, "prune_builds"):
            try:
                result["builder_cache"] = client.api.prune_builds()
            except APIError:
                result["builder_cache"] = {
                    "warning": "Build cache pruning is not supported by the current Docker daemon.",
                }
        else:
            result["builder_cache"] = {
                "warning": "Build cache pruning is not available on this Docker SDK.",
            }
    return result


__all__ = [
    "APIError",
    "NotFound",
    "kill_container",
    "pause_container",
    "prune_system",
    "remove_container",
    "remove_image",
    "restart_container",
    "start_container",
    "stop_container",
    "unpause_container",
]
