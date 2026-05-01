from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlmodel import select
from starlette.concurrency import run_in_threadpool

from backend.app.api.auth import User, get_current_user
from backend.app.db import session_scope
from backend.app.models.audit_log import AuditLog
from backend.app.models.user import User as UserModel

router = APIRouter(prefix="/api/audit", tags=["audit"])

ALLOWED_RESOURCE_TYPES = {"service", "deploy", "user", "project", "system", "volume", "network", "image"}


class AuditEntry(BaseModel):
    id: UUID
    action: str
    resource_type: str
    resource_id: str
    actor_id: UUID | None = None
    actor_name: str | None = None
    actor_email: str | None = None
    created_at: str
    details: dict = Field(default_factory=dict)


class AuditPage(BaseModel):
    items: list[AuditEntry]
    total: int


def _list_audit_sync(
    current_user: User,
    limit: int,
    offset: int,
    actor_id: UUID | None,
    resource_type: str | None,
    resource_id: str | None,
    action: str | None,
    since: datetime | None,
    until: datetime | None,
) -> AuditPage:
    with session_scope() as session:
        statement = select(AuditLog)

        if not current_user.is_owner:
            # non-owners only see actions they performed
            statement = statement.where(AuditLog.actor_id == current_user.id)
        if actor_id is not None:
            statement = statement.where(AuditLog.actor_id == actor_id)
        if resource_type:
            statement = statement.where(AuditLog.resource_type == resource_type)
        if resource_id:
            statement = statement.where(AuditLog.resource_id == resource_id)
        if action:
            statement = statement.where(AuditLog.action.startswith(action))
        if since is not None:
            statement = statement.where(AuditLog.created_at >= since)
        if until is not None:
            statement = statement.where(AuditLog.created_at <= until)

        total_rows = session.exec(statement).all()
        total = len(total_rows)
        page_rows = (
            session.exec(statement.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)).all()
        )

        actor_ids = {row.actor_id for row in page_rows if row.actor_id is not None}
        actors: dict[UUID, UserModel] = {}
        if actor_ids:
            user_rows = session.exec(select(UserModel).where(UserModel.id.in_(actor_ids))).all()
            actors = {user.id: user for user in user_rows}

        items = [
            AuditEntry(
                id=row.id,
                action=row.action,
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                actor_id=row.actor_id,
                actor_name=actors.get(row.actor_id).full_name if row.actor_id in actors else None,
                actor_email=actors.get(row.actor_id).email if row.actor_id in actors else None,
                created_at=row.created_at.isoformat(),
                details=row.details or {},
            )
            for row in page_rows
        ]
        return AuditPage(items=items, total=total)


@router.get("", response_model=AuditPage)
async def list_audit_entries(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    actor_id: UUID | None = Query(default=None),
    resource_type: str | None = Query(default=None, max_length=100),
    resource_id: str | None = Query(default=None, max_length=255),
    action: str | None = Query(default=None, max_length=255),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    current_user: User = Depends(get_current_user),
) -> AuditPage:
    if resource_type and resource_type not in ALLOWED_RESOURCE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"resource_type must be one of: {', '.join(sorted(ALLOWED_RESOURCE_TYPES))}",
        )
    return await run_in_threadpool(
        _list_audit_sync,
        current_user,
        limit,
        offset,
        actor_id,
        resource_type,
        resource_id,
        action,
        since,
        until,
    )
