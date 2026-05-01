from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Column, DateTime
from sqlmodel import Field, Relationship, SQLModel

from backend.app.models.mixins import TimestampedModel, UUIDPrimaryKey

if TYPE_CHECKING:
    from backend.app.models.project import Project
    from backend.app.models.user import User


class Invite(UUIDPrimaryKey, TimestampedModel, SQLModel, table=True):
    """A one-shot invitation that grants a new or existing user access to a project.

    `accepted_at` is null until the invitee accepts. After acceptance, the
    record stays as an audit trail of who joined what and when.
    """

    __tablename__ = "invites"

    token: str = Field(index=True, unique=True, nullable=False, max_length=64)
    email: str = Field(index=True, nullable=False, max_length=320)
    project_id: UUID = Field(foreign_key="projects.id", nullable=False, index=True)
    role: str = Field(default="member", nullable=False, max_length=32)
    full_name_hint: str | None = Field(default=None, max_length=255)
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    accepted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    accepted_by_user_id: UUID | None = Field(default=None, foreign_key="users.id")
    created_by_user_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)
    revoked_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    project: "Project" = Relationship()
    accepted_by: "User" = Relationship(sa_relationship_kwargs={"foreign_keys": "Invite.accepted_by_user_id"})
    created_by: "User" = Relationship(sa_relationship_kwargs={"foreign_keys": "Invite.created_by_user_id"})
