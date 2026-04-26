"""Adaptive Score Engine v1 — feedback-based score adjustment.

First layer of adaptive intelligence in Atlas. Reads stored user feedback on a
single (source, reference_id) pair and returns a deterministic, fixed-magnitude
score adjustment.

Mapping:
    positive  → +1.0
    important → +2.0
    negative  → -2.0
    none / unknown / missing event → 0.0 (neutral)

Properties:
    - Deterministic: same inputs → same output.
    - Fail-safe: any error returns a neutral adjustment.
    - Isolated: does not modify ranking, classifiers, or any other module.
    - Read-only: never writes to the database.

# FUTURE:
# Este módulo será expandido para:
# - agregação de múltiplos feedbacks
# - aprendizado por categoria/source
# - decaimento temporal
# - perfil de usuário
# NÃO implementar isso nesta etapa
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.modules.memory.models import MemoryEvent

logger = get_logger("modules.memory.scoring")


# Fixed adjustment table — single source of truth for feedback weights.
# Any feedback value not present here resolves to a neutral 0.0 adjustment.
_FEEDBACK_ADJUSTMENT: dict[str, float] = {
    "positive": 1.0,
    "important": 2.0,
    "negative": -2.0,
}


@dataclass
class MemoryAdjustment:
    adjustment: float
    reason: Optional[str] = None


def compute_memory_adjustment(
    source: str,
    reference_id: str,
    base_score: float,
    *,
    db_session: Session,
) -> MemoryAdjustment:
    """Return a deterministic score adjustment derived from stored feedback.

    Looks up the most recent MemoryEvent matching (source, reference_id) that
    carries non-null feedback. Maps the feedback signal to a fixed adjustment
    via _FEEDBACK_ADJUSTMENT. Returns MemoryAdjustment(0.0, None) when there is
    no event, no feedback, an unknown feedback value, or any error.

    base_score is part of the public signature so that future revisions can
    scale or clamp adjustments without breaking callers — see the FUTURE
    comment at the top of this module. v1 does not use it.
    """
    try:
        if not source or not reference_id:
            return MemoryAdjustment(0.0, None)

        event = (
            db_session.query(MemoryEvent)
            .filter(
                MemoryEvent.source == source,
                MemoryEvent.reference_id == reference_id,
                MemoryEvent.feedback.isnot(None),
            )
            .order_by(MemoryEvent.created_at.desc())
            .first()
        )

        if event is None or event.feedback is None:
            return MemoryAdjustment(0.0, None)

        adjustment = _FEEDBACK_ADJUSTMENT.get(event.feedback)
        if adjustment is None:
            return MemoryAdjustment(0.0, None)

        return MemoryAdjustment(adjustment, event.feedback)
    except Exception as exc:
        logger.warning(
            "compute_memory_adjustment falhou [%s/%s]: %s",
            source, reference_id, exc,
        )
        return MemoryAdjustment(0.0, None)
