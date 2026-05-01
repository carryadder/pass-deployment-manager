"""Centralized RBAC checks.

Effective project role for a user, in priority order:
- system owner (`User.is_owner`)        -> "admin"
- project owner (`Project.owner_id`)    -> "admin"
- explicit project_members.role         -> "admin" | "member" | "viewer"
- otherwise                             -> None (no access)

The view/modify helpers below are the only place where access logic lives.
Routers should call them rather than inlining `is_owner` checks.
"""

from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, select

from backend.app.models.project import Project
from backend.app.models.project_member import ProjectMember
from backend.app.models.user import User


VALID_PROJECT_ROLES = ("admin", "member", "viewer")


def get_effective_role(session: Session, user: User, project: Project) -> str | None:
    if user.is_owner:
        return "admin"
    if project.owner_id == user.id:
        return "admin"
    membership = session.exec(
        select(ProjectMember).where(
            ProjectMember.project_id == project.id,
            ProjectMember.user_id == user.id,
        )
    ).first()
    if membership is None:
        return None
    return membership.role


def can_view_project(session: Session, user: User, project: Project) -> bool:
    return get_effective_role(session, user, project) is not None


def can_modify_project(session: Session, user: User, project: Project) -> bool:
    role = get_effective_role(session, user, project)
    return role in {"admin", "member"}


def can_admin_project(session: Session, user: User, project: Project) -> bool:
    return get_effective_role(session, user, project) == "admin"


def list_visible_project_ids(session: Session, user: User) -> list[UUID]:
    """All project ids the user can read."""
    if user.is_owner:
        return [project.id for project in session.exec(select(Project)).all()]
    owned = [project.id for project in session.exec(select(Project).where(Project.owner_id == user.id)).all()]
    member_rows = session.exec(
        select(ProjectMember).where(ProjectMember.user_id == user.id)
    ).all()
    return list({*owned, *(row.project_id for row in member_rows)})


__all__ = [
    "VALID_PROJECT_ROLES",
    "can_admin_project",
    "can_modify_project",
    "can_view_project",
    "get_effective_role",
    "list_visible_project_ids",
]
