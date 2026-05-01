from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

from backend.app.models.mixins import TimestampedModel, UUIDPrimaryKey

if TYPE_CHECKING:
    from backend.app.models.user import User


class AuditLog(UUIDPrimaryKey, TimestampedModel, SQLModel, table=True):
    __tablename__ = "audit_logs"

    actor_id: UUID | None = Field(default=None, foreign_key="users.id", index=True)
    action: str = Field(nullable=False, max_length=255)
    resource_type: str = Field(nullable=False, max_length=100)
    resource_id: str = Field(nullable=False, max_length=255)
    details: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )

    actor: "User | None" = Relationship(back_populates="audit_logs")
