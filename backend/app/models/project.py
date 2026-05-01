from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel

from backend.app.models.mixins import TimestampedModel, UUIDPrimaryKey

if TYPE_CHECKING:
    from backend.app.models.service import Service
    from backend.app.models.user import User


class Project(UUIDPrimaryKey, TimestampedModel, SQLModel, table=True):
    __tablename__ = "projects"

    name: str = Field(index=True, unique=True, nullable=False, max_length=255)
    slug: str = Field(index=True, unique=True, nullable=False, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    owner_id: UUID = Field(foreign_key="users.id", nullable=False, index=True)

    owner: "User" = Relationship(back_populates="projects")
    services: list["Service"] = Relationship(back_populates="project")
