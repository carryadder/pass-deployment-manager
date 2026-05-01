from fastapi import APIRouter, HTTPException
from docker.errors import DockerException

from backend.app.config import get_settings
from backend.app.core.docker_client import get_docker_info, ping_docker

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/info")
def system_info() -> dict:
    try:
        return get_docker_info()
    except DockerException as exc:
        raise HTTPException(status_code=503, detail="Docker daemon is unavailable") from exc


@router.get("/ping")
def system_ping() -> dict:
    return {"docker_available": ping_docker()}


@router.get("/config")
def system_config() -> dict:
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "app_debug": settings.app_debug,
        "docker_host": settings.docker_host,
    }

