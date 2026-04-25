"""Tests for Memory Module v1.

Covers:
- event creation
- idempotency (no duplicate on event_type + reference_id)
- update of existing event
- list with filters
- add_feedback
- memory failure does NOT break inbox flow
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.modules.memory.repository import MemoryRepository
from app.modules.memory.service import MemoryService


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def memory_svc(db_session):
    return MemoryService(db_session)


# ── Creation ──────────────────────────────────────────────────────────────────

def test_log_event_creates_record(memory_svc, db_session):
    memory_svc.log_event(
        event_type="email_classified",
        source="email",
        reference_id="msg_001",
        payload={"category": "action", "priority": "alta"},
        score=80.0,
    )
    events = memory_svc.get_recent_events()
    assert len(events) == 1
    assert events[0].event_type == "email_classified"
    assert events[0].source == "email"
    assert events[0].reference_id == "msg_001"
    assert events[0].score == 80.0


def test_log_event_payload_serialized_as_json(memory_svc):
    payload = {"category": "finance", "priority": "alta", "tags": ["PIX"], "reason": ["keyword"]}
    memory_svc.log_event(
        event_type="email_classified",
        source="email",
        reference_id="msg_002",
        payload=payload,
    )
    events = memory_svc.get_recent_events()
    assert len(events) == 1
    parsed = json.loads(events[0].payload)
    assert parsed["category"] == "finance"
    assert parsed["tags"] == ["PIX"]


def test_log_event_without_score(memory_svc):
    memory_svc.log_event(
        event_type="news_ranked",
        source="news",
        reference_id="https://example.com/news/1",
        payload={"title": "Mercado hoje", "category": "macro"},
    )
    events = memory_svc.get_recent_events()
    assert events[0].score is None


def test_log_event_without_reference_id(memory_svc):
    memory_svc.log_event(
        event_type="system_check",
        source="system",
        reference_id=None,
        payload={"status": "ok"},
    )
    events = memory_svc.get_recent_events()
    assert len(events) == 1
    assert events[0].reference_id is None


# ── Idempotency ───────────────────────────────────────────────────────────────

def test_log_event_idempotent_same_type_and_ref(memory_svc, db_session):
    """Same event_type + reference_id must update, not create a duplicate."""
    memory_svc.log_event(
        event_type="email_classified",
        source="email",
        reference_id="msg_dup",
        payload={"category": "update", "priority": "baixa"},
        score=10.0,
    )
    memory_svc.log_event(
        event_type="email_classified",
        source="email",
        reference_id="msg_dup",
        payload={"category": "action", "priority": "alta"},
        score=90.0,
    )
    events = memory_svc.get_recent_events()
    assert len(events) == 1
    assert events[0].score == 90.0
    parsed = json.loads(events[0].payload)
    assert parsed["priority"] == "alta"


def test_different_reference_ids_create_separate_events(memory_svc):
    memory_svc.log_event("email_classified", "email", "ref_a", {"cat": "action"})
    memory_svc.log_event("email_classified", "email", "ref_b", {"cat": "update"})
    events = memory_svc.get_recent_events()
    assert len(events) == 2


def test_different_event_types_same_ref_create_separate_events(memory_svc):
    memory_svc.log_event("email_classified", "email", "ref_x", {"cat": "action"})
    memory_svc.log_event("email_followup", "email", "ref_x", {"cat": "action"})
    events = memory_svc.get_recent_events()
    assert len(events) == 2


# ── Update ────────────────────────────────────────────────────────────────────

def test_update_preserves_created_at(memory_svc, db_session):
    memory_svc.log_event("email_classified", "email", "ref_upd", {"v": 1}, score=10.0)
    first = memory_svc.get_recent_events()[0]
    created_at_before = first.created_at

    memory_svc.log_event("email_classified", "email", "ref_upd", {"v": 2}, score=20.0)
    updated = memory_svc.get_recent_events()[0]

    assert updated.created_at == created_at_before
    assert updated.score == 20.0


# ── List with filters ─────────────────────────────────────────────────────────

def test_list_filter_by_event_type(memory_svc):
    memory_svc.log_event("email_classified", "email", "e1", {})
    memory_svc.log_event("news_ranked", "news", "n1", {})

    email_events = memory_svc.get_recent_events(event_type="email_classified")
    assert len(email_events) == 1
    assert email_events[0].event_type == "email_classified"


def test_list_filter_by_source(memory_svc):
    memory_svc.log_event("email_classified", "email", "e2", {})
    memory_svc.log_event("news_ranked", "news", "n2", {})

    news_events = memory_svc.get_recent_events(source="news")
    assert len(news_events) == 1
    assert news_events[0].source == "news"


def test_list_limit(memory_svc):
    for i in range(10):
        memory_svc.log_event("test_event", "test", f"ref_{i}", {})
    events = memory_svc.get_recent_events(limit=3)
    assert len(events) == 3


def test_list_no_filter_returns_all(memory_svc):
    memory_svc.log_event("email_classified", "email", "r1", {})
    memory_svc.log_event("news_ranked", "news", "r2", {})
    assert len(memory_svc.get_recent_events()) == 2


# ── Feedback ──────────────────────────────────────────────────────────────────

def test_add_feedback_updates_existing_event(memory_svc):
    memory_svc.log_event("email_classified", "email", "fb_ref", {"cat": "action"})
    memory_svc.add_feedback("fb_ref", "positive")
    events = memory_svc.get_recent_events()
    assert events[0].feedback == "positive"


def test_add_feedback_does_not_create_new_event(memory_svc):
    memory_svc.log_event("email_classified", "email", "fb_ref2", {})
    memory_svc.add_feedback("fb_ref2", "negative")
    assert len(memory_svc.get_recent_events()) == 1


def test_add_feedback_on_missing_ref_is_silent(memory_svc):
    """Calling add_feedback with an unknown reference_id must not raise."""
    memory_svc.add_feedback("nonexistent_ref", "positive")


# ── Fail-safe ─────────────────────────────────────────────────────────────────

def test_log_event_repo_failure_does_not_raise(db_session):
    """Repository failure must be silently swallowed by the service."""
    svc = MemoryService(db_session)
    svc._repo = MagicMock()
    svc._repo.get_by_type_and_ref.side_effect = RuntimeError("DB explodiu")

    svc.log_event("email_classified", "email", "ref_fail", {"cat": "action"})


def test_get_recent_events_repo_failure_returns_empty(db_session):
    svc = MemoryService(db_session)
    svc._repo = MagicMock()
    svc._repo.list_events.side_effect = RuntimeError("DB explodiu")

    result = svc.get_recent_events()
    assert result == []


def test_add_feedback_repo_failure_does_not_raise(db_session):
    svc = MemoryService(db_session)
    svc._repo = MagicMock()
    svc._repo.get_by_reference.side_effect = RuntimeError("DB explodiu")

    svc.add_feedback("any_ref", "positive")


# ── Critical: memory failure does NOT break inbox ─────────────────────────────

def test_inbox_summarize_emails_survives_memory_failure():
    """InboxService.summarize_emails() must return normally even if memory logging fails."""
    from app.integrations.email_models import EmailMessage
    from app.modules.inbox.service import InboxService

    real_email = EmailMessage(
        id="msg_test",
        sender="test@example.com",
        subject="Reunião amanhã",
        snippet="Confirma presença",
        priority="baixa",
        timestamp="2026-04-25T10:00:00",
        is_read=False,
    )

    mock_client = MagicMock()
    mock_client.list_recent_emails.return_value = [real_email]

    with patch(
        "app.db.session.SessionLocal",
        side_effect=RuntimeError("DB completamente indisponivel"),
    ):
        svc = InboxService(client=mock_client)
        result = svc.summarize_emails()

    assert "total" in result
    assert result["total"] == 1


# ── Repository direct tests ───────────────────────────────────────────────────

def test_repository_create_and_get(db_session):
    repo = MemoryRepository(db_session)
    event = repo.create(
        event_type="email_classified",
        source="email",
        reference_id="repo_ref",
        payload='{"cat": "action"}',
        score=75.0,
    )
    assert event.id is not None
    fetched = repo.get_by_type_and_ref("email_classified", "repo_ref")
    assert fetched is not None
    assert fetched.score == 75.0


def test_repository_get_by_reference_returns_all_events(db_session):
    repo = MemoryRepository(db_session)
    repo.create("type_a", "src", "shared_ref", "{}", 10.0)
    repo.create("type_b", "src", "shared_ref", "{}", 20.0)
    results = repo.get_by_reference("shared_ref")
    assert len(results) == 2


def test_repository_list_events_with_combined_filters(db_session):
    repo = MemoryRepository(db_session)
    repo.create("email_classified", "email", "r1", "{}", 10.0)
    repo.create("email_classified", "news", "r2", "{}", 20.0)
    repo.create("news_ranked", "news", "r3", "{}", 30.0)

    results = repo.list_events(event_type="email_classified", source="email")
    assert len(results) == 1
    assert results[0].reference_id == "r1"
