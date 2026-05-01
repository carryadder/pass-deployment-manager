from typing import TYPE_CHECKING
from uuid import UUID

from sqlmodel import Field, Relationship, SQLModel

from backend.app.models.mixins import TimestampedModel, UUIDPrimaryKey

if TYPE_CHECKING:
    from backend.app.models.service import Service


class Deploy(UUIDPrimaryKey, TimestampedModel, SQLModel, table=True):
    __tablename__ = "deploys"

    service_id: UUID = Field(foreign_key="services.id", nullable=False, index=True)
    status: str = Field(default="pending", nullable=False, max_length=50)
    source_type: str = Field(nullable=False, max_length=50)
    source_ref: str | None = Field(default=None, max_length=500)
    image_tag: str | None = Field(default=None, max_length=500)

    service: "Service" = Relationship(back_populates="deploys")
