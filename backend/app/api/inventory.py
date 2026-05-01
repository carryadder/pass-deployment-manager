from fastapi import APIRouter, HTTPException
from docker.errors import DockerException
from starlette.concurrency import run_in_threadpool

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
async def get_containers() -> list[dict]:
    try:
        return await run_in_threadpool(list_containers)
    except DockerException as exc:
        raise HTTPException(status_code=503, detail="Docker daemon is unavailable") from exc


@router.get("/api/containers/{container_id}")
async def get_container(container_id: str) -> dict:
    try:
        return await run_in_threadpool(inspect_container, container_id)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail="Container not found") from exc
    except DockerException as exc:
        raise HTTPException(status_code=503, detail="Docker daemon is unavailable") from exc


@router.get("/api/images")
async def get_images() -> list[dict]:
    try:
        return await run_in_threadpool(list_images)
    except DockerException as exc:
        raise HTTPException(status_code=503, detail="Docker daemon is unavailable") from exc


@router.get("/api/volumes")
async def get_volumes() -> list[dict]:
    try:
        return await run_in_threadpool(list_volumes)
    except DockerException as exc:
        raise HTTPException(status_code=503, detail="Docker daemon is unavailable") from exc


@router.get("/api/networks")
async def get_networks() -> list[dict]:
    try:
        return await run_in_threadpool(list_networks)
    except DockerException as exc:
        raise HTTPException(status_code=503, detail="Docker daemon is unavailable") from exc
