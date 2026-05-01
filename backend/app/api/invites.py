from __future__ import annotations

import secrets as secrets_module
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlmodel import select
from starlette.concurrency import run_in_threadpool

from backend.app.api.auth import (
    TokenResponse,
    User,
    create_access_token,
    create_refresh_token,
    get_current_user,
    hash_password,
)
from backend.app.core.access import VALID_PROJECT_ROLES, can_admin_project, list_visible_project_ids
from backend.app.db import session_scope
from backend.app.models.audit_log import AuditLog
from backend.app.models.invite import Invite
from backend.app.models.project import Project
from backend.app.models.project_member import ProjectMember
from backend.app.models.user import User as UserModel

router = APIRouter(prefix="/api/invites", tags=["invites"])

DEFAULT_EXPIRY_HOURS = 72


class InviteCreateRequest(BaseModel):
    email: EmailStr
    project_id: UUID
    role: str = Field(default="member")
    full_name_hint: str | None = Field(default=None, max_length=255)
    expires_in_hours: int = Field(default=DEFAULT_EXPIRY_HOURS, ge=1, le=24 * 30)

    @field_validator("role")
    @classmethod
    def _validate_role(cls, value: str) -> str:
        if value not in VALID_PROJECT_ROLES:
            raise ValueError(f"role must be one of: {', '.join(VALID_PROJECT_ROLES)}")
        return value


class InviteAcceptRequest(BaseModel):
    token: str = Field(min_length=8, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)


class InvitePreviewResponse(BaseModel):
    email: EmailStr
    project_id: UUID
    project_name: str
    role: str
    full_name_hint: str | None = None
    invited_by_name: str | None = None
    expires_at: str
    accepted_at: str | None = None
    revoked_at: str | None = None


class InviteSummary(BaseModel):
    id: UUID
    email: EmailStr
    project_id: UUID
    project_name: str
    role: str
    full_name_hint: str | None = None
    expires_at: str
    accepted_at: str | None = None
    revoked_at: str | None = None
    accept_url: str
    token: str
    created_at: str


def _generate_token() -> str:
    return secrets_module.token_urlsafe(24)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _summarize(invite: Invite, project: Project, base_url: str) -> InviteSummary:
    return InviteSummary(
        id=invite.id,
        email=invite.email,
        project_id=project.id,
        project_name=project.name,
        role=invite.role,
        full_name_hint=invite.full_name_hint,
        expires_at=invite.expires_at.isoformat(),
        accepted_at=invite.accepted_at.isoformat() if invite.accepted_at else None,
        revoked_at=invite.revoked_at.isoformat() if invite.revoked_at else None,
        accept_url=f"{base_url}/accept-invite/{invite.token}",
        token=invite.token,
        created_at=invite.created_at.isoformat(),
    )


def _create_invite_sync(payload: InviteCreateRequest, current_user: User) -> InviteSummary:
    with session_scope() as session:
        project = session.get(Project, payload.project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        if not can_admin_project(session, current_user, project):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only project admins can issue invites",
            )

        # if email already maps to an existing active user, just add them as a member
        existing_user = session.exec(
            select(UserModel).where(UserModel.email == payload.email.lower())
        ).first()
        if existing_user is not None and existing_user.is_active:
            # ensure membership row exists (or update role)
            existing_membership = session.exec(
                select(ProjectMember).where(
                    ProjectMember.project_id == project.id,
                    ProjectMember.user_id == existing_user.id,
                )
            ).first()
            if existing_membership is None:
                session.add(
                    ProjectMember(
                        project_id=project.id,
                        user_id=existing_user.id,
                        role=payload.role,
                    )
                )
            else:
                existing_membership.role = payload.role
                session.add(existing_membership)
            invite = Invite(
                token=_generate_token(),
                email=payload.email.lower(),
                project_id=project.id,
                role=payload.role,
                full_name_hint=payload.full_name_hint,
                expires_at=_now() + timedelta(hours=payload.expires_in_hours),
                accepted_at=_now(),
                accepted_by_user_id=existing_user.id,
                created_by_user_id=current_user.id,
            )
            session.add(invite)
            session.add(
                AuditLog(
                    actor_id=current_user.id,
                    action="project.invite.auto_attach",
                    resource_type="project",
                    resource_id=str(project.id),
                    details={"email": payload.email, "user_id": str(existing_user.id), "role": payload.role},
                )
            )
            session.commit()
            session.refresh(invite)
            return _summarize(invite, project, base_url="")

        invite = Invite(
            token=_generate_token(),
            email=payload.email.lower(),
            project_id=project.id,
            role=payload.role,
            full_name_hint=payload.full_name_hint,
            expires_at=_now() + timedelta(hours=payload.expires_in_hours),
            created_by_user_id=current_user.id,
        )
        session.add(invite)
        session.add(
            AuditLog(
                actor_id=current_user.id,
                action="project.invite.create",
                resource_type="project",
                resource_id=str(project.id),
                details={"email": payload.email, "role": payload.role, "expires_in_hours": payload.expires_in_hours},
            )
        )
        session.commit()
        session.refresh(invite)
        return _summarize(invite, project, base_url="")


@router.post("", response_model=InviteSummary, status_code=status.HTTP_201_CREATED)
async def create_invite(
    payload: InviteCreateRequest,
    current_user: User = Depends(get_current_user),
) -> InviteSummary:
    return await run_in_threadpool(_create_invite_sync, payload, current_user)


def _list_invites_sync(current_user: User, project_id: UUID | None) -> list[InviteSummary]:
    with session_scope() as session:
        statement = select(Invite)
        if project_id is not None:
            statement = statement.where(Invite.project_id == project_id)
        if current_user.is_owner:
            invites = session.exec(statement.order_by(Invite.created_at.desc())).all()
        else:
            visible_ids = list_visible_project_ids(session, current_user)
            if not visible_ids:
                return []
            invites = session.exec(
                statement.where(Invite.project_id.in_(visible_ids)).order_by(Invite.created_at.desc())
            ).all()
        results: list[InviteSummary] = []
        for invite in invites:
            project = session.get(Project, invite.project_id)
            if project is None:
                continue
            results.append(_summarize(invite, project, base_url=""))
        return results


@router.get("", response_model=list[InviteSummary])
async def list_invites(
    project_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
) -> list[InviteSummary]:
    return await run_in_threadpool(_list_invites_sync, current_user, project_id)


def _revoke_invite_sync(invite_id: UUID, current_user: User) -> dict:
    with session_scope() as session:
        invite = session.get(Invite, invite_id)
        if invite is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
        project = session.get(Project, invite.project_id)
        if project is None or not can_admin_project(session, current_user, project):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot revoke this invite")
        if invite.accepted_at is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invite already accepted")
        invite.revoked_at = _now()
        session.add(invite)
        session.add(
            AuditLog(
                actor_id=current_user.id,
                action="project.invite.revoke",
                resource_type="project",
                resource_id=str(project.id),
                details={"invite_id": str(invite.id), "email": invite.email},
            )
        )
        session.commit()
        return {"revoked": True, "invite_id": str(invite_id)}


@router.delete("/{invite_id}")
async def revoke_invite(
    invite_id: UUID,
    current_user: User = Depends(get_current_user),
) -> dict:
    return await run_in_threadpool(_revoke_invite_sync, invite_id, current_user)


def _preview_invite_sync(token: str) -> InvitePreviewResponse:
    with session_scope() as session:
        invite = session.exec(select(Invite).where(Invite.token == token)).first()
        if invite is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
        project = session.get(Project, invite.project_id)
        creator = session.get(UserModel, invite.created_by_user_id)
        return InvitePreviewResponse(
            email=invite.email,
            project_id=invite.project_id,
            project_name=project.name if project is not None else "(deleted project)",
            role=invite.role,
            full_name_hint=invite.full_name_hint,
            invited_by_name=creator.full_name if creator is not None else None,
            expires_at=invite.expires_at.isoformat(),
            accepted_at=invite.accepted_at.isoformat() if invite.accepted_at else None,
            revoked_at=invite.revoked_at.isoformat() if invite.revoked_at else None,
        )


@router.get("/preview/{token}", response_model=InvitePreviewResponse)
async def preview_invite(token: str) -> InvitePreviewResponse:
    return await run_in_threadpool(_preview_invite_sync, token)


def _accept_invite_sync(payload: InviteAcceptRequest) -> TokenResponse:
    with session_scope() as session:
        invite = session.exec(select(Invite).where(Invite.token == payload.token)).first()
        if invite is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found")
        if invite.revoked_at is not None:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invite has been revoked")
        if invite.accepted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Invite has already been accepted"
            )
        if invite.expires_at < _now():
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invite has expired")
        project = session.get(Project, invite.project_id)
        if project is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Invite project no longer exists"
            )

        existing_user = session.exec(
            select(UserModel).where(UserModel.email == invite.email)
        ).first()
        if existing_user is not None:
            user = existing_user
        else:
            user = UserModel(
                email=invite.email,
                password_hash=hash_password(payload.password),
                full_name=payload.full_name,
                is_active=True,
                is_owner=False,
            )
            session.add(user)
            session.flush()

        existing_membership = session.exec(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id, ProjectMember.user_id == user.id
            )
        ).first()
        if existing_membership is None:
            session.add(
                ProjectMember(project_id=project.id, user_id=user.id, role=invite.role)
            )
        else:
            existing_membership.role = invite.role
            session.add(existing_membership)

        invite.accepted_at = _now()
        invite.accepted_by_user_id = user.id
        session.add(invite)
        session.add(
            AuditLog(
                actor_id=user.id,
                action="project.invite.accept",
                resource_type="project",
                resource_id=str(project.id),
                details={"invite_id": str(invite.id), "email": invite.email, "role": invite.role},
            )
        )
        session.commit()
        session.refresh(user)

        claims = {"email": user.email, "is_owner": user.is_owner}
        return TokenResponse(
            access_token=create_access_token(str(user.id), extra_claims=claims),
            refresh_token=create_refresh_token(str(user.id), extra_claims=claims),
        )


@router.post("/accept", response_model=TokenResponse)
async def accept_invite(payload: InviteAcceptRequest) -> TokenResponse:
    return await run_in_threadpool(_accept_invite_sync, payload)
