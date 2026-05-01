from collections.abc import Callable

import docker
from docker import DockerClient
from docker.errors import DockerException

from backend.app.config import get_settings


def get_docker_client() -> DockerClient:
    settings = get_settings()
    if settings.docker_host:
        return docker.DockerClient(base_url=settings.docker_host)
    return docker.from_env()


def ping_docker(client_factory: Callable[[], DockerClient] = get_docker_client) -> bool:
    client = client_factory()
    try:
        client.ping()
    except DockerException:
        return False
    return True


def get_docker_info(client_factory: Callable[[], DockerClient] = get_docker_client) -> dict:
    client = client_factory()
    return client.info()

