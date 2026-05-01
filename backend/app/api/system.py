import shutil

from fastapi import APIRouter, HTTPException
from docker.errors import DockerException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from backend.app.config import get_settings
from backend.app.core.docker_client import get_docker_info, ping_docker

router = APIRouter(prefix="/api/system", tags=["system"])


class HostDiskUsage(BaseModel):
    total_bytes: int
    used_bytes: int
    free_bytes: int
    mountpoint: str


class HostSummary(BaseModel):
    name: str | None = None
    operating_system: str | None = None
    architecture: str | None = None
    kernel_version: str | None = None
    docker_version: str | None = None
    api_version: str | None = None
    storage_driver: str | None = None
    cgroup_version: str | None = None
    cpu_count: int | None = None
    memory_total_bytes: int | None = None
    containers_total: int | None = None
    containers_running: int | None = None
    containers_paused: int | None = None
    containers_stopped: int | None = None
    images_total: int | None = None
    disk: HostDiskUsage | None = None


def _gather_host_summary() -> HostSummary:
    info = get_docker_info()
    docker_root_dir = info.get("DockerRootDir") or "/"
    disk_payload: HostDiskUsage | None = None
    try:
        usage = shutil.disk_usage(docker_root_dir)
        disk_payload = HostDiskUsage(
            total_bytes=usage.total,
            used_bytes=usage.used,
            free_bytes=usage.free,
            mountpoint=docker_root_dir,
        )
    except (OSError, FileNotFoundError):
        disk_payload = None

    return HostSummary(
        name=info.get("Name"),
        operating_system=info.get("OperatingSystem"),
        architecture=info.get("Architecture"),
        kernel_version=info.get("KernelVersion"),
        docker_version=info.get("ServerVersion"),
        api_version=info.get("ApiVersion") or info.get("Version"),
        storage_driver=info.get("Driver"),
        cgroup_version=info.get("CgroupVersion"),
        cpu_count=info.get("NCPU"),
        memory_total_bytes=info.get("MemTotal"),
        containers_total=info.get("Containers"),
        containers_running=info.get("ContainersRunning"),
        containers_paused=info.get("ContainersPaused"),
        containers_stopped=info.get("ContainersStopped"),
        images_total=info.get("Images"),
        disk=disk_payload,
    )


@router.get("/info")
async def system_info() -> dict:
    try:
        return await run_in_threadpool(get_docker_info)
    except DockerException as exc:
        raise HTTPException(status_code=503, detail="Docker daemon is unavailable") from exc


@router.get("/host", response_model=HostSummary)
async def system_host() -> HostSummary:
    try:
        return await run_in_threadpool(_gather_host_summary)
    except DockerException as exc:
        raise HTTPException(status_code=503, detail="Docker daemon is unavailable") from exc


@router.get("/ping")
async def system_ping() -> dict:
    return {"docker_available": await run_in_threadpool(ping_docker)}


@router.get("/config")
async def system_config() -> dict:
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "app_debug": settings.app_debug,
        "docker_host": settings.docker_host,
    }
