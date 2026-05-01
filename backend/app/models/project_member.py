from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel

from backend.app.models.mixins import TimestampedModel, UUIDPrimaryKey

if TYPE_CHECKING:
    from backend.app.models.project import Project
    from backend.app.models.user import User


class ProjectMember(UUIDPrimaryKey, TimestampedModel, SQLModel, table=True):
    """Per-project membership.

    Roles: 'admin' (manage members + deploy), 'member' (deploy + edit env),
    'viewer' (read-only). Project owners are not stored here; the
    `Project.owner_id` column already represents the owning user, and they
    always have effective 'admin' access.
    """

    __tablename__ = "project_members"

    project_id: UUID = Field(foreign_key="projects.id", nullable=False, index=True)
    user_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)
    role: str = Field(default="member", nullable=False, max_length=32)

    project: "Project" = Relationship()
    user: "User" = Relationship()
