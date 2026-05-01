from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampedModel(SQLModel):
    created_at: datetime = Field(
        default_factory=utcnow,
        nullable=False,
        sa_type=DateTime(timezone=True),
    )
    updated_at: datetime = Field(
        default_factory=utcnow,
        nullable=False,
        sa_type=DateTime(timezone=True),
    )


class UUIDPrimaryKey(SQLModel):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
