"""Pydantic schemas for memory events."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MemoryEventResponse(BaseModel):
    id: int
    created_at: datetime
    updated_at: datetime
    event_type: str
    source: str
    reference_id: str | None
    payload: str  # raw JSON string — deserialized by caller if needed
    score: float | None
    feedback: str | None

    model_config = ConfigDict(from_attributes=True)
