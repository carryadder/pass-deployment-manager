from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel

from backend.app.models.mixins import TimestampedModel, UUIDPrimaryKey

if TYPE_CHECKING:
    from backend.app.models.service import Service


class EnvVar(UUIDPrimaryKey, TimestampedModel, SQLModel, table=True):
    __tablename__ = "env_vars"

    service_id: UUID = Field(foreign_key="services.id", nullable=False, index=True)
    key: str = Field(nullable=False, max_length=255)
    value: str = Field(nullable=False, max_length=4000)
    is_secret: bool = Field(default=False, nullable=False)

    service: "Service" = Relationship(back_populates="env_vars")
