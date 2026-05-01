from typing import TYPE_CHECKING

from sqlmodel import Field, Relationship, SQLModel

from backend.app.models.mixins import TimestampedModel, UUIDPrimaryKey

if TYPE_CHECKING:
    from backend.app.models.audit_log import AuditLog
    from backend.app.models.project import Project


class User(UUIDPrimaryKey, TimestampedModel, SQLModel, table=True):
    __tablename__ = "users"

    email: str = Field(index=True, unique=True, nullable=False, max_length=320)
    password_hash: str = Field(nullable=False, max_length=255)
    full_name: str = Field(nullable=False, max_length=255)
    is_active: bool = Field(default=True, nullable=False)
    is_owner: bool = Field(default=False, nullable=False)

    projects: list["Project"] = Relationship(back_populates="owner")
    audit_logs: list["AuditLog"] = Relationship(back_populates="actor")
