from __future__ import annotations

import asyncio
import threading
from uuid import UUID

from fastapi import APIRouter, WebSocket
from jose import JWTError
from sqlmodel import Session
from starlette.websockets import WebSocketDisconnect

from backend.app.api.auth import decode_access_token
from backend.app.db import engine
from backend.app.models.service import Service
from backend.app.models.user import User
from backend.app.core.docker_client import get_docker_client

router = APIRouter()


def _resolve_token(websocket: WebSocket) -> str | None:
    authorization = websocket.headers.get("authorization")
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return websocket.query_params.get("token")


def _authenticate_websocket(websocket: WebSocket) -> User:
    token = _resolve_token(websocket)
    if not token:
        raise PermissionError("Missing bearer token")

    try:
        payload = decode_access_token(token)
        user_id = UUID(payload["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise PermissionError("Invalid or expired token") from exc

    with Session(engine) as session:
        user = session.get(User, user_id)
        if user is None or not user.is_active:
            raise PermissionError("User is not authorized for websocket access")
        return user


def _get_service(service_id: UUID) -> Service | None:
    with Session(engine) as session:
        return session.get(Service, service_id)


def _get_container_for_service(service: Service):
    client = get_docker_client()
    containers = client.containers.list(
        all=True,
        filters={"label": f"dmgr.service.slug={service.slug}"},
    )
    return containers[0] if containers else None


async def _send_log_history(websocket: WebSocket, container, tail: int) -> None:
    history = container.logs(tail=tail)
    if isinstance(history, bytes):
        text = history.decode("utf-8", errors="replace")
    else:
        text = str(history)

    for line in text.splitlines():
        await websocket.send_text(line)


async def _stream_follow_logs(websocket: WebSocket, container, tail: int) -> None:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[tuple[str, str | None]] = asyncio.Queue()
    stop_event = threading.Event()

    def producer() -> None:
        try:
            for chunk in container.logs(stream=True, follow=True, tail=tail):
                if stop_event.is_set():
                    break
                text = chunk.decode("utf-8", errors="replace").rstrip("\n")
                asyncio.run_coroutine_threadsafe(queue.put(("log", text)), loop)
        except Exception as exc:  # pragma: no cover - runtime Docker path
            asyncio.run_coroutine_threadsafe(queue.put(("error", str(exc))), loop)
        finally:
            asyncio.run_coroutine_threadsafe(queue.put(("done", None)), loop)

    thread = threading.Thread(target=producer, daemon=True)
    thread.start()

    async def watch_disconnect() -> None:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                stop_event.set()
                break

    disconnect_task = asyncio.create_task(watch_disconnect())

    try:
        while True:
            event, payload = await queue.get()
            if event == "log" and payload is not None:
                await websocket.send_text(payload)
            elif event == "error" and payload is not None:
                await websocket.send_text(f"[log-stream-error] {payload}")
                break
            elif event == "done":
                break
    except WebSocketDisconnect:
        stop_event.set()
    finally:
        stop_event.set()
        disconnect_task.cancel()
        thread.join(timeout=1)


@router.websocket("/api/services/{service_id}/logs")
async def service_logs(websocket: WebSocket, service_id: UUID) -> None:
    try:
        _authenticate_websocket(websocket)
    except PermissionError as exc:
        await websocket.close(code=4401, reason=str(exc))
        return

    service = _get_service(service_id)
    if service is None:
        await websocket.close(code=4404, reason="Service not found")
        return

    container = _get_container_for_service(service)
    if container is None:
        await websocket.close(code=4404, reason="Container not found for service")
        return

    tail_value = websocket.query_params.get("tail", "200")
    follow_value = websocket.query_params.get("follow", "true")
    try:
        tail = max(0, int(tail_value))
    except ValueError:
        tail = 200
    follow = follow_value.lower() != "false"

    await websocket.accept()

    await _send_log_history(websocket, container, tail=tail)
    if follow:
        await _stream_follow_logs(websocket, container, tail=0)
    else:
        await websocket.close()
