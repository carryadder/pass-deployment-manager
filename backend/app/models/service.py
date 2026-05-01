from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

from backend.app.models.mixins import TimestampedModel, UUIDPrimaryKey

if TYPE_CHECKING:
    from backend.app.models.deploy import Deploy
    from backend.app.models.env_var import EnvVar
    from backend.app.models.project import Project
    from backend.app.models.secret import Secret


class Service(UUIDPrimaryKey, TimestampedModel, SQLModel, table=True):
    __tablename__ = "services"

    name: str = Field(index=True, nullable=False, max_length=255)
    slug: str = Field(index=True, unique=True, nullable=False, max_length=255)
    image: str = Field(nullable=False, max_length=500)
    status: str = Field(default="created", nullable=False, max_length=50)
    project_id: UUID = Field(foreign_key="projects.id", nullable=False, index=True)
    config: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default="{}"),
    )

    project: "Project" = Relationship(back_populates="services")
    deploys: list["Deploy"] = Relationship(back_populates="service")
    env_vars: list["EnvVar"] = Relationship(back_populates="service")
    secrets: list["Secret"] = Relationship(back_populates="service")
