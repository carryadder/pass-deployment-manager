from fastapi import APIRouter, HTTPException, Query
from docker.errors import DockerException

from backend.app.core.lifecycle import (
    APIError,
    NotFound,
    kill_container,
    pause_container,
    prune_system,
    remove_container,
    remove_image,
    restart_container,
    start_container,
    stop_container,
    unpause_container,
)

router = APIRouter(tags=["lifecycle"])


def _handle_container_action(action) -> dict:
    try:
        return action()
    except NotFound as exc:
        raise HTTPException(status_code=404, detail="Container not found") from exc
    except APIError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DockerException as exc:
        raise HTTPException(status_code=503, detail="Docker daemon is unavailable") from exc


@router.post("/api/containers/{container_id}/start")
def post_start_container(container_id: str) -> dict:
    return _handle_container_action(lambda: start_container(container_id))


@router.post("/api/containers/{container_id}/stop")
def post_stop_container(container_id: str) -> dict:
    return _handle_container_action(lambda: stop_container(container_id))


@router.post("/api/containers/{container_id}/restart")
def post_restart_container(container_id: str) -> dict:
    return _handle_container_action(lambda: restart_container(container_id))


@router.post("/api/containers/{container_id}/kill")
def post_kill_container(container_id: str) -> dict:
    return _handle_container_action(lambda: kill_container(container_id))


@router.post("/api/containers/{container_id}/pause")
def post_pause_container(container_id: str) -> dict:
    return _handle_container_action(lambda: pause_container(container_id))


@router.post("/api/containers/{container_id}/unpause")
def post_unpause_container(container_id: str) -> dict:
    return _handle_container_action(lambda: unpause_container(container_id))


@router.delete("/api/containers/{container_id}")
def delete_container(
    container_id: str,
    force: bool = Query(default=False),
    volumes: bool = Query(default=False),
) -> dict:
    return _handle_container_action(
        lambda: remove_container(container_id, force=force, volumes=volumes)
    )


@router.delete("/api/images/{image_id}")
def delete_image(image_id: str, force: bool = Query(default=False)) -> dict:
    try:
        return remove_image(image_id, force=force)
    except NotFound as exc:
        raise HTTPException(status_code=404, detail="Image not found") from exc
    except APIError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DockerException as exc:
        raise HTTPException(status_code=503, detail="Docker daemon is unavailable") from exc


@router.post("/api/system/prune")
def post_system_prune() -> dict:
    try:
        return prune_system()
    except APIError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except DockerException as exc:
        raise HTTPException(status_code=503, detail="Docker daemon is unavailable") from exc
