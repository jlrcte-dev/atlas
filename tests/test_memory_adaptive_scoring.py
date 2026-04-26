"""Tests for Adaptive Score Engine v1 — app.modules.memory.scoring.

Coverage:
- no event for (source, reference_id) → 0.0
- event without feedback → 0.0
- positive feedback → +1.0
- important feedback → +2.0
- negative feedback → -2.0
- unknown feedback value → 0.0
- source isolation (feedback on news must not leak to email)
- empty inputs → 0.0
- DB error → 0.0 (fail-safe)
- determinism (same input → same output; base_score does not affect result)
"""
from __future__ import annotations

from unittest.mock import MagicMock

from app.modules.memory.scoring import (
    MemoryAdjustment,
    compute_memory_adjustment,
)
from app.modules.memory.service import MemoryService


# ── Helpers ───────────────────────────────────────────────────────────────────

def _seed_event(
    svc: MemoryService,
    source: str,
    ref: str,
    feedback: str | None,
) -> None:
    """Insert a memory event and (optionally) attach feedback to it."""
    svc.log_event(
        event_type=f"{source}_ranked",
        source=source,
        reference_id=ref,
        payload={"title": "X"},
        score=5.0,
    )
    if feedback is not None:
        svc.add_feedback(ref, feedback, source=source)


# ── Neutral cases ─────────────────────────────────────────────────────────────

def test_no_event_returns_zero(db_session):
    result = compute_memory_adjustment(
        "news", "missing_ref", 0.0, db_session=db_session
    )
    assert isinstance(result, MemoryAdjustment)
    assert result.adjustment == 0.0
    assert result.reason is None


def test_event_without_feedback_returns_zero(db_session):
    svc = MemoryService(db_session)
    _seed_event(svc, "news", "ref_a", feedback=None)

    result = compute_memory_adjustment(
        "news", "ref_a", 0.0, db_session=db_session
    )
    assert result.adjustment == 0.0
    assert result.reason is None


def test_unknown_feedback_value_returns_zero(db_session):
    svc = MemoryService(db_session)
    _seed_event(svc, "news", "ref_weird", feedback="kindof")

    result = compute_memory_adjustment(
        "news", "ref_weird", 0.0, db_session=db_session
    )
    assert result.adjustment == 0.0
    assert result.reason is None


# ── Mapped feedback values ────────────────────────────────────────────────────

def test_positive_feedback_returns_plus_one(db_session):
    svc = MemoryService(db_session)
    _seed_event(svc, "news", "ref_pos", feedback="positive")

    result = compute_memory_adjustment(
        "news", "ref_pos", 0.0, db_session=db_session
    )
    assert result.adjustment == 1.0
    assert result.reason == "positive"


def test_important_feedback_returns_plus_two(db_session):
    svc = MemoryService(db_session)
    _seed_event(svc, "news", "ref_imp", feedback="important")

    result = compute_memory_adjustment(
        "news", "ref_imp", 0.0, db_session=db_session
    )
    assert result.adjustment == 2.0
    assert result.reason == "important"


def test_negative_feedback_returns_minus_two(db_session):
    svc = MemoryService(db_session)
    _seed_event(svc, "news", "ref_neg", feedback="negative")

    result = compute_memory_adjustment(
        "news", "ref_neg", 0.0, db_session=db_session
    )
    assert result.adjustment == -2.0
    assert result.reason == "negative"


# ── Isolation ─────────────────────────────────────────────────────────────────

def test_source_isolation(db_session):
    """Feedback on one source must not leak into another source's lookup."""
    svc = MemoryService(db_session)
    _seed_event(svc, "news", "shared_ref", feedback="positive")

    result = compute_memory_adjustment(
        "email", "shared_ref", 0.0, db_session=db_session
    )
    assert result.adjustment == 0.0
    assert result.reason is None


def test_empty_inputs_return_zero(db_session):
    """Defensive: empty source or empty reference_id returns neutral."""
    assert (
        compute_memory_adjustment("", "ref", 0.0, db_session=db_session).adjustment
        == 0.0
    )
    assert (
        compute_memory_adjustment("news", "", 0.0, db_session=db_session).adjustment
        == 0.0
    )


# ── Fail-safe ─────────────────────────────────────────────────────────────────

def test_db_error_returns_zero():
    """Any exception from the session must be caught and yield a neutral result."""
    bad_session = MagicMock()
    bad_session.query.side_effect = RuntimeError("db down")

    result = compute_memory_adjustment(
        "news", "ref", 0.0, db_session=bad_session
    )
    assert result.adjustment == 0.0
    assert result.reason is None


# ── Determinism ───────────────────────────────────────────────────────────────

def test_determinism_same_input_same_output(db_session):
    svc = MemoryService(db_session)
    _seed_event(svc, "news", "ref_det", feedback="important")

    a = compute_memory_adjustment("news", "ref_det", 0.0, db_session=db_session)
    b = compute_memory_adjustment("news", "ref_det", 0.0, db_session=db_session)
    # base_score must NOT change the output in v1
    c = compute_memory_adjustment("news", "ref_det", 99.5, db_session=db_session)

    assert a == b == c
    assert a.adjustment == 2.0
    assert a.reason == "important"
