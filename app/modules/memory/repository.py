"""Memory event repository."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.modules.memory.models import MemoryEvent


class MemoryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        event_type: str,
        source: str,
        reference_id: str | None,
        payload: str,
        score: float | None = None,
        feedback: str | None = None,
    ) -> MemoryEvent:
        event = MemoryEvent(
            event_type=event_type,
            source=source,
            reference_id=reference_id,
            payload=payload,
            score=score,
            feedback=feedback,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def get_by_type_and_ref(self, event_type: str, reference_id: str) -> MemoryEvent | None:
        return (
            self.db.query(MemoryEvent)
            .filter(
                MemoryEvent.event_type == event_type,
                MemoryEvent.reference_id == reference_id,
            )
            .first()
        )

    def get_by_reference(self, reference_id: str) -> list[MemoryEvent]:
        return (
            self.db.query(MemoryEvent)
            .filter(MemoryEvent.reference_id == reference_id)
            .order_by(MemoryEvent.created_at.desc())
            .all()
        )

    def update(self, event: MemoryEvent, **kwargs: object) -> MemoryEvent:
        for key, value in kwargs.items():
            setattr(event, key, value)
        event.updated_at = datetime.now(UTC)
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event

    def list_events(
        self,
        event_type: str | None = None,
        source: str | None = None,
        reference_id: str | None = None,
        limit: int = 50,
    ) -> list[MemoryEvent]:
        q = self.db.query(MemoryEvent)
        if event_type:
            q = q.filter(MemoryEvent.event_type == event_type)
        if source:
            q = q.filter(MemoryEvent.source == source)
        if reference_id:
            q = q.filter(MemoryEvent.reference_id == reference_id)
        return q.order_by(MemoryEvent.created_at.desc()).limit(limit).all()
