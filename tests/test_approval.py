"""Tests for the approval system."""

import pytest

from app.core.exceptions import ActionAlreadyResolvedError
from app.modules.approval.service import ApprovalService

# ── Creation ──────────────────────────────────────────────────────


def test_create_email_draft(db_session):
    draft = ApprovalService(db_session).create_email_draft(
        {"to": "a@b.com", "subject": "test", "body": "hello"}
    )
    assert draft.id is not None
    assert draft.status == "pending"
    assert draft.type == "draft_email"


def test_create_event_proposal(db_session):
    draft = ApprovalService(db_session).create_event_proposal(
        {"title": "Meeting", "start": "10:00", "end": "11:00"}
    )
    assert draft.id is not None
    assert draft.status == "pending"
    assert draft.type == "create_event"


# ── Resolution ────────────────────────────────────────────────────


def test_confirm_sets_approved(db_session):
    svc = ApprovalService(db_session)
    draft = svc.create_email_draft({"to": "a@b.com", "subject": "t", "body": "b"})
    updated = svc.confirm(draft)
    assert updated.status == "approved"
    assert updated.resolved_at is not None


def test_reject_sets_rejected(db_session):
    svc = ApprovalService(db_session)
    draft = svc.create_email_draft({"to": "a@b.com", "subject": "t", "body": "b"})
    updated = svc.reject(draft)
    assert updated.status == "rejected"
    assert updated.resolved_at is not None


# ── Double-resolution guard ───────────────────────────────────────


def test_cannot_approve_already_approved(db_session):
    svc = ApprovalService(db_session)
    draft = svc.create_email_draft({"to": "a@b.com", "subject": "t", "body": "b"})
    svc.confirm(draft)
    with pytest.raises(ActionAlreadyResolvedError):
        svc.confirm(draft)


def test_cannot_reject_already_rejected(db_session):
    svc = ApprovalService(db_session)
    draft = svc.create_email_draft({"to": "a@b.com", "subject": "t", "body": "b"})
    svc.reject(draft)
    with pytest.raises(ActionAlreadyResolvedError):
        svc.reject(draft)


def test_cannot_reject_already_approved(db_session):
    svc = ApprovalService(db_session)
    draft = svc.create_email_draft({"to": "a@b.com", "subject": "t", "body": "b"})
    svc.confirm(draft)
    with pytest.raises(ActionAlreadyResolvedError):
        svc.reject(draft)


# ── Queries ───────────────────────────────────────────────────────


def test_list_pending(db_session):
    svc = ApprovalService(db_session)
    svc.create_email_draft({"to": "a@b.com", "subject": "t1", "body": "b1"})
    svc.create_event_proposal({"title": "M", "start": "10:00", "end": "11:00"})
    pending = svc.list_pending()
    assert len(pending) == 2


def test_list_pending_excludes_resolved(db_session):
    svc = ApprovalService(db_session)
    d1 = svc.create_email_draft({"to": "a@b.com", "subject": "t1", "body": "b1"})
    svc.create_event_proposal({"title": "M", "start": "10:00", "end": "11:00"})
    svc.confirm(d1)
    pending = svc.list_pending()
    assert len(pending) == 1


def test_get_draft_found(db_session):
    svc = ApprovalService(db_session)
    draft = svc.create_email_draft({"to": "a@b.com", "subject": "t", "body": "b"})
    assert svc.get_draft(draft.id) is not None


def test_get_draft_not_found(db_session):
    assert ApprovalService(db_session).get_draft(9999) is None
