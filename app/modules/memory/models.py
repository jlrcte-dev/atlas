"""ORM model for memory events."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class MemoryEvent(Base):
    __tablename__ = "memory_events"
    __table_args__ = (
        UniqueConstraint("event_type", "reference_id", name="uq_memory_event_type_ref"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    event_type: Mapped[str] = mapped_column(String(100), index=True)
    source: Mapped[str] = mapped_column(String(100), index=True)
    reference_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    payload: Mapped[str] = mapped_column(Text, default="{}")  # JSON serialized dict
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback: Mapped[str | None] = mapped_column(String(50), nullable=True)
