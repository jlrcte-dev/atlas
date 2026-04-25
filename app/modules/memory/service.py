"""Memory service — passive observer, fail-safe event logging."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.modules.memory.repository import MemoryRepository
from app.modules.memory.schemas import MemoryEventResponse

logger = get_logger("modules.memory")


class MemoryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._repo = MemoryRepository(db)

    def log_event(
        self,
        event_type: str,
        source: str,
        reference_id: Optional[str],
        payload: dict,
        score: Optional[float] = None,
    ) -> None:
        """Log a system event. Idempotent on (event_type, reference_id). Fail-safe."""
        try:
            payload_json = json.dumps(payload, ensure_ascii=False, default=str)

            if reference_id:
                existing = self._repo.get_by_type_and_ref(event_type, reference_id)
                if existing:
                    self._repo.update(
                        existing,
                        payload=payload_json,
                        score=score,
                        updated_at=datetime.now(UTC),
                    )
                    return

            self._repo.create(
                event_type=event_type,
                source=source,
                reference_id=reference_id,
                payload=payload_json,
                score=score,
            )
        except Exception as exc:
            logger.warning(
                "Memory log_event falhou [%s/%s]: %s", event_type, reference_id, exc
            )

    def add_feedback(
        self,
        reference_id: str,
        feedback: str,
        *,
        source: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> bool:
        """Set feedback on an existing event. Fail-safe. Does not create a new event.

        Optional `source` / `event_type` disambiguate when the same reference_id
        is shared across event types (e.g., hash collisions). When `event_type` is
        given, the unique (event_type, reference_id) index is used directly.

        Returns True iff an event was found and updated; False on miss or error.
        """
        try:
            if event_type:
                event = self._repo.get_by_type_and_ref(event_type, reference_id)
                events = [event] if event else []
            else:
                events = self._repo.get_by_reference(reference_id)
                if source:
                    events = [e for e in events if e.source == source]
            if not events:
                logger.warning(
                    "Memory add_feedback: nenhum evento para ref=%s", reference_id
                )
                return False
            self._repo.update(events[0], feedback=feedback)
            return True
        except Exception as exc:
            logger.warning(
                "Memory add_feedback falhou [ref=%s]: %s", reference_id, exc
            )
            return False

    def get_recent_events(
        self,
        source: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[MemoryEventResponse]:
        """Return recent events with optional filters. Fail-safe (returns [] on error)."""
        try:
            events = self._repo.list_events(
                event_type=event_type,
                source=source,
                limit=limit,
            )
            return [MemoryEventResponse.model_validate(e) for e in events]
        except Exception as exc:
            logger.warning("Memory get_recent_events falhou: %s", exc)
            return []
