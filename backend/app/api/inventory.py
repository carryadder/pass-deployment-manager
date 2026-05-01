from fastapi import APIRouter, HTTPException, Query, status
from docker.errors import APIError, DockerException
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from backend.app.core.inventory import (
    NotFound,
    create_network,
    create_volume,
    inspect_container,
    list_containers,
    list_images,
    list_networks,
    list_volumes,
    remove_network,
    remove_volume,
)

router = APIRouter(tags=["inventory"])


class VolumeCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    driver: str = Field(default="local", min_length=1, max_length=255)
    labels: dict[str, str] = Field(default_factory=dict)
    options: dict[str, str] = Field(default_factory=dict)


class NetworkCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    driver: str = Field(default="bridge", min_length=1, max_length=255)
    internal: bool = False
    attachable: bool = False
    labels: dict[str, str] = Field(default_factory=dict)
    options: dict[str, str] = Field(default_factory=dict)


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


@router.post("/api/volumes", status_code=status.HTTP_201_CREATED)
async def post_volume(payload: VolumeCreateRequest) -> dict:
    try:
        return await run_in_threadpool(
            create_volume,
            payload.name,
            payload.driver,
            payload.labels,
            payload.options,
        )
    except APIError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DockerException as exc:
        raise HTTPException(status_code=503, detail="Docker daemon is unavailable") from exc


@router.delete("/api/volumes/{name}")
async def delete_volume(name: str, force: bool = Query(default=False)) -> dict:
    try:
        return await run_in_threadpool(remove_volume, name, force)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail="Volume not found") from exc
    except APIError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DockerException as exc:
        raise HTTPException(status_code=503, detail="Docker daemon is unavailable") from exc


@router.get("/api/networks")
async def get_networks() -> list[dict]:
    try:
        return await run_in_threadpool(list_networks)
    except DockerException as exc:
        raise HTTPException(status_code=503, detail="Docker daemon is unavailable") from exc


@router.post("/api/networks", status_code=status.HTTP_201_CREATED)
async def post_network(payload: NetworkCreateRequest) -> dict:
    try:
        return await run_in_threadpool(
            create_network,
            payload.name,
            payload.driver,
            payload.internal,
            payload.attachable,
            payload.labels,
            payload.options,
        )
    except APIError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DockerException as exc:
        raise HTTPException(status_code=503, detail="Docker daemon is unavailable") from exc


@router.delete("/api/networks/{name}")
async def delete_network(name: str) -> dict:
    try:
        return await run_in_threadpool(remove_network, name)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail="Network not found") from exc
    except APIError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DockerException as exc:
        raise HTTPException(status_code=503, detail="Docker daemon is unavailable") from exc
