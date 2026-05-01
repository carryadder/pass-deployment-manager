from __future__ import annotations

from uuid import UUID

from fastapi import WebSocket
from jose import JWTError

from backend.app.api.auth import decode_access_token
from backend.app.db import session_scope
from backend.app.models.project import Project
from backend.app.models.service import Service
from backend.app.models.user import User


def resolve_token(websocket: WebSocket) -> str | None:
    authorization = websocket.headers.get("authorization")
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return websocket.query_params.get("token")


def authenticate_websocket(websocket: WebSocket) -> User:
    token = resolve_token(websocket)
    if not token:
        raise PermissionError("Missing bearer token")

    try:
        payload = decode_access_token(token)
        user_id = UUID(payload["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise PermissionError("Invalid or expired token") from exc

    with session_scope() as session:
        user = session.get(User, user_id)
        if user is None or not user.is_active:
            raise PermissionError("User is not authorized for websocket access")
        return user


def get_service_for_user(service_id: UUID, user: User) -> Service:
    with session_scope() as session:
        service = session.get(Service, service_id)
        if service is None:
            raise LookupError("Service not found")

        project = session.get(Project, service.project_id)
        if project is None:
            raise LookupError("Project not found for service")
        if project.owner_id != user.id and not user.is_owner:
            raise PermissionError("Not allowed to access this service")
        return service


__all__ = ["authenticate_websocket", "get_service_for_user"]
