from fastapi import APIRouter, HTTPException
from docker.errors import DockerException

from backend.app.core.inventory import (
    NotFound,
    inspect_container,
    list_containers,
    list_images,
    list_networks,
    list_volumes,
)

router = APIRouter(tags=["inventory"])


@router.get("/api/containers")
def get_containers() -> list[dict]:
    try:
        return list_containers()
    except DockerException as exc:
        raise HTTPException(status_code=503, detail="Docker daemon is unavailable") from exc


@router.get("/api/containers/{container_id}")
def get_container(container_id: str) -> dict:
    try:
        return inspect_container(container_id)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail="Container not found") from exc
    except DockerException as exc:
        raise HTTPException(status_code=503, detail="Docker daemon is unavailable") from exc


@router.get("/api/images")
def get_images() -> list[dict]:
    try:
        return list_images()
    except DockerException as exc:
        raise HTTPException(status_code=503, detail="Docker daemon is unavailable") from exc


@router.get("/api/volumes")
def get_volumes() -> list[dict]:
    try:
        return list_volumes()
    except DockerException as exc:
        raise HTTPException(status_code=503, detail="Docker daemon is unavailable") from exc


@router.get("/api/networks")
def get_networks() -> list[dict]:
    try:
        return list_networks()
    except DockerException as exc:
        raise HTTPException(status_code=503, detail="Docker daemon is unavailable") from exc
