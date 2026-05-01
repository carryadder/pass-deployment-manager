from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect

from backend.app.core.metrics import metrics_sampler
from backend.app.ws.common import authenticate_websocket, get_service_for_user

router = APIRouter()


@router.websocket("/api/services/{service_id}/metrics")
async def service_metrics(websocket: WebSocket, service_id: UUID) -> None:
    try:
        user = await asyncio.to_thread(authenticate_websocket, websocket)
    except PermissionError as exc:
        await websocket.close(code=4401, reason=str(exc))
        return

    try:
        await asyncio.to_thread(get_service_for_user, service_id, user)
    except PermissionError as exc:
        await websocket.close(code=4403, reason=str(exc))
        return
    except LookupError:
        await websocket.close(code=4404, reason="Service not found")
        return

    range_value = websocket.query_params.get("range", "5m")
    await websocket.accept()

    history = await asyncio.to_thread(metrics_sampler.get_history, service_id, range_value)
    for sample in history:
        await websocket.send_json(sample)

    queue: asyncio.Queue[dict] = asyncio.Queue()
    loop = asyncio.get_running_loop()
    metrics_sampler.subscribe(service_id, loop, queue)

    try:
        while True:
            sample = await queue.get()
            await websocket.send_json(sample)
    except WebSocketDisconnect:
        pass
    finally:
        metrics_sampler.unsubscribe(service_id, queue)
