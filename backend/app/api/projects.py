from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from starlette.concurrency import run_in_threadpool

from backend.app.api.auth import User, get_current_user
from backend.app.core.access import (
    VALID_PROJECT_ROLES,
    can_admin_project,
    can_view_project,
    list_visible_project_ids,
)
from backend.app.db import session_scope
from backend.app.models.audit_log import AuditLog
from backend.app.models.project import Project
from backend.app.models.project_member import ProjectMember
from backend.app.models.service import Service
from backend.app.models.user import User as UserModel

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class ProjectSummary(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None = None
    owner_id: UUID
    owner_email: str | None = None
    role: str
    created_at: str
    service_count: int
    member_count: int


class ProjectMemberEntry(BaseModel):
    user_id: UUID
    email: EmailStr
    full_name: str
    role: str
    is_owner: bool = False
    joined_at: str | None = None


class ProjectMemberAddRequest(BaseModel):
    user_id: UUID
    role: str = Field(default="member")

    @field_validator("role")
    @classmethod
    def _validate_role(cls, value: str) -> str:
        if value not in VALID_PROJECT_ROLES:
            raise ValueError(f"role must be one of: {', '.join(VALID_PROJECT_ROLES)}")
        return value


class ProjectMemberUpdateRequest(BaseModel):
    role: str = Field(default="member")

    @field_validator("role")
    @classmethod
    def _validate_role(cls, value: str) -> str:
        if value not in VALID_PROJECT_ROLES:
            raise ValueError(f"role must be one of: {', '.join(VALID_PROJECT_ROLES)}")
        return value


def _slugify(name: str) -> str:
    slug = "-".join(name.lower().strip().split())
    return "".join(ch for ch in slug if ch.isalnum() or ch == "-").strip("-") or "project"


def _summarize_project(session, project: Project, role: str) -> ProjectSummary:
    services = session.exec(select(Service).where(Service.project_id == project.id)).all()
    members = session.exec(
        select(ProjectMember).where(ProjectMember.project_id == project.id)
    ).all()
    owner_user = session.get(UserModel, project.owner_id)
    return ProjectSummary(
        id=project.id,
        name=project.name,
        slug=project.slug,
        description=project.description,
        owner_id=project.owner_id,
        owner_email=owner_user.email if owner_user is not None else None,
        role=role,
        created_at=project.created_at.isoformat(),
        service_count=len(services),
        member_count=len(members) + 1,  # owner counts
    )


def _list_projects_sync(current_user: User) -> list[ProjectSummary]:
    with session_scope() as session:
        ids = list_visible_project_ids(session, current_user)
        if not ids:
            return []
        projects = session.exec(select(Project).where(Project.id.in_(ids))).all()
        items: list[ProjectSummary] = []
        for project in sorted(projects, key=lambda p: p.created_at, reverse=True):
            if project.owner_id == current_user.id or current_user.is_owner:
                role = "admin"
            else:
                membership = session.exec(
                    select(ProjectMember).where(
                        ProjectMember.project_id == project.id,
                        ProjectMember.user_id == current_user.id,
                    )
                ).first()
                role = membership.role if membership is not None else "viewer"
            items.append(_summarize_project(session, project, role))
        return items


@router.get("", response_model=list[ProjectSummary])
async def list_projects(current_user: User = Depends(get_current_user)) -> list[ProjectSummary]:
    return await run_in_threadpool(_list_projects_sync, current_user)


def _create_project_sync(payload: ProjectCreateRequest, current_user: User) -> ProjectSummary:
    if not current_user.is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the workspace owner can create new projects in v0.1.",
        )
    with session_scope() as session:
        slug = _slugify(payload.name)
        # ensure unique slug
        for suffix in range(0, 32):
            candidate = slug if suffix == 0 else f"{slug}-{suffix}"
            existing = session.exec(select(Project).where(Project.slug == candidate)).first()
            if existing is None:
                slug = candidate
                break
        project = Project(
            name=payload.name,
            slug=slug,
            description=payload.description,
            owner_id=current_user.id,
        )
        session.add(project)
        session.add(
            AuditLog(
                actor_id=current_user.id,
                action="project.create",
                resource_type="project",
                resource_id=str(project.id),
                details={"name": payload.name, "slug": slug},
            )
        )
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Project name or slug already exists"
            ) from exc
        session.refresh(project)
        return _summarize_project(session, project, "admin")


@router.post("", response_model=ProjectSummary, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateRequest,
    current_user: User = Depends(get_current_user),
) -> ProjectSummary:
    return await run_in_threadpool(_create_project_sync, payload, current_user)


def _list_members_sync(project_id: UUID, current_user: User) -> list[ProjectMemberEntry]:
    with session_scope() as session:
        project = session.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        if not can_view_project(session, current_user, project):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to view this project")

        entries: list[ProjectMemberEntry] = []
        owner = session.get(UserModel, project.owner_id)
        if owner is not None:
            entries.append(
                ProjectMemberEntry(
                    user_id=owner.id,
                    email=owner.email,
                    full_name=owner.full_name,
                    role="admin",
                    is_owner=True,
                    joined_at=project.created_at.isoformat(),
                )
            )
        memberships = session.exec(
            select(ProjectMember).where(ProjectMember.project_id == project_id)
        ).all()
        for membership in memberships:
            user = session.get(UserModel, membership.user_id)
            if user is None:
                continue
            entries.append(
                ProjectMemberEntry(
                    user_id=user.id,
                    email=user.email,
                    full_name=user.full_name,
                    role=membership.role,
                    is_owner=False,
                    joined_at=membership.created_at.isoformat(),
                )
            )
        return entries


@router.get("/{project_id}/members", response_model=list[ProjectMemberEntry])
async def list_project_members(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
) -> list[ProjectMemberEntry]:
    return await run_in_threadpool(_list_members_sync, project_id, current_user)


def _add_member_sync(
    project_id: UUID, payload: ProjectMemberAddRequest, current_user: User
) -> ProjectMemberEntry:
    with session_scope() as session:
        project = session.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        if not can_admin_project(session, current_user, project):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Only project admins can add members"
            )
        target = session.get(UserModel, payload.user_id)
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        if target.id == project.owner_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="User is already the project owner"
            )
        existing = session.exec(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id,
                ProjectMember.user_id == target.id,
            )
        ).first()
        if existing is not None:
            existing.role = payload.role
            session.add(existing)
            membership = existing
        else:
            membership = ProjectMember(
                project_id=project.id, user_id=target.id, role=payload.role
            )
            session.add(membership)
        session.add(
            AuditLog(
                actor_id=current_user.id,
                action="project.member.add",
                resource_type="project",
                resource_id=str(project.id),
                details={"target_user_id": str(target.id), "role": payload.role},
            )
        )
        session.commit()
        session.refresh(membership)
        return ProjectMemberEntry(
            user_id=target.id,
            email=target.email,
            full_name=target.full_name,
            role=membership.role,
            is_owner=False,
            joined_at=membership.created_at.isoformat(),
        )


@router.post("/{project_id}/members", response_model=ProjectMemberEntry, status_code=status.HTTP_201_CREATED)
async def add_project_member(
    project_id: UUID,
    payload: ProjectMemberAddRequest,
    current_user: User = Depends(get_current_user),
) -> ProjectMemberEntry:
    return await run_in_threadpool(_add_member_sync, project_id, payload, current_user)


def _update_member_sync(
    project_id: UUID, user_id: UUID, payload: ProjectMemberUpdateRequest, current_user: User
) -> ProjectMemberEntry:
    with session_scope() as session:
        project = session.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        if not can_admin_project(session, current_user, project):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Only project admins can change roles"
            )
        membership = session.exec(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id, ProjectMember.user_id == user_id
            )
        ).first()
        if membership is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
        membership.role = payload.role
        session.add(membership)
        session.add(
            AuditLog(
                actor_id=current_user.id,
                action="project.member.update",
                resource_type="project",
                resource_id=str(project.id),
                details={"target_user_id": str(user_id), "role": payload.role},
            )
        )
        session.commit()
        session.refresh(membership)
        target = session.get(UserModel, user_id)
        return ProjectMemberEntry(
            user_id=user_id,
            email=target.email if target is not None else "",
            full_name=target.full_name if target is not None else "",
            role=membership.role,
            is_owner=False,
            joined_at=membership.created_at.isoformat(),
        )


@router.patch("/{project_id}/members/{user_id}", response_model=ProjectMemberEntry)
async def update_project_member(
    project_id: UUID,
    user_id: UUID,
    payload: ProjectMemberUpdateRequest,
    current_user: User = Depends(get_current_user),
) -> ProjectMemberEntry:
    return await run_in_threadpool(_update_member_sync, project_id, user_id, payload, current_user)


def _remove_member_sync(project_id: UUID, user_id: UUID, current_user: User) -> dict:
    with session_scope() as session:
        project = session.get(Project, project_id)
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        if not can_admin_project(session, current_user, project):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Only project admins can remove members"
            )
        if project.owner_id == user_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="The project owner cannot be removed"
            )
        membership = session.exec(
            select(ProjectMember).where(
                ProjectMember.project_id == project.id, ProjectMember.user_id == user_id
            )
        ).first()
        if membership is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
        session.delete(membership)
        session.add(
            AuditLog(
                actor_id=current_user.id,
                action="project.member.remove",
                resource_type="project",
                resource_id=str(project.id),
                details={"target_user_id": str(user_id)},
            )
        )
        session.commit()
        return {"removed": True, "user_id": str(user_id)}


@router.delete("/{project_id}/members/{user_id}")
async def remove_project_member(
    project_id: UUID,
    user_id: UUID,
    current_user: User = Depends(get_current_user),
) -> dict:
    return await run_in_threadpool(_remove_member_sync, project_id, user_id, current_user)
