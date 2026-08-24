"""Shared model mixins: UUID PKs, timestamps, JSONB."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.engine import Base

GenUUID = lambda: uuid.uuid4()  # noqa: E731


def now_utc() -> datetime:
    return datetime.now(UTC)


class UUIDMixin(Base):
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=GenUUID)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc, nullable=False
    )


class JSONMixin:
    """raw_metadata JSONB column present on many business tables."""

    raw_metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
