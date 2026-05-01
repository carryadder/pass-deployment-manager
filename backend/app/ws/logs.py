from __future__ import annotations

import asyncio
import threading
from uuid import UUID

from fastapi import APIRouter, WebSocket
from starlette.concurrency import run_in_threadpool
from starlette.websockets import WebSocketDisconnect

from backend.app.models.service import Service
from backend.app.core.docker_client import get_docker_client
from backend.app.ws.common import authenticate_websocket, get_service_for_user

router = APIRouter()


def _get_container_for_service(service: Service):
    client = get_docker_client()
    containers = client.containers.list(
        all=True,
        filters={"label": f"dmgr.service.slug={service.slug}"},
    )
    return containers[0] if containers else None


async def _send_log_history(websocket: WebSocket, container, tail: int) -> None:
    history = await run_in_threadpool(container.logs, tail=tail)
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
        user = await run_in_threadpool(authenticate_websocket, websocket)
    except PermissionError as exc:
        await websocket.close(code=4401, reason=str(exc))
        return

    try:
        service = await run_in_threadpool(get_service_for_user, service_id, user)
    except PermissionError as exc:
        await websocket.close(code=4403, reason=str(exc))
        return
    except LookupError:
        await websocket.close(code=4404, reason="Service not found")
        return

    container = await run_in_threadpool(_get_container_for_service, service)
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
