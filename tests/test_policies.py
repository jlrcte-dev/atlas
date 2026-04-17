"""Tests for policy engine and related core modules (permissions, security)."""

from app.core.permissions import ActionType
from app.core.security import SecurityPolicy, security_policy
from app.orchestrator.policies import is_read_only, requires_approval


def test_requires_approval_for_send_email():
    assert requires_approval(ActionType.SEND_EMAIL) is True


def test_requires_approval_for_create_event():
    assert requires_approval(ActionType.CREATE_EVENT) is True


def test_no_approval_required_for_read_actions():
    assert requires_approval(ActionType.READ_EMAILS) is False
    assert requires_approval(ActionType.READ_CALENDAR) is False
    assert requires_approval(ActionType.READ_NEWS) is False


def test_is_read_only_for_read_actions():
    assert is_read_only(ActionType.READ_EMAILS) is True
    assert is_read_only(ActionType.READ_CALENDAR) is True
    assert is_read_only(ActionType.READ_NEWS) is True
    assert is_read_only(ActionType.GENERATE_BRIEFING) is True


def test_is_read_only_false_for_write_actions():
    assert is_read_only(ActionType.SEND_EMAIL) is False
    assert is_read_only(ActionType.CREATE_EVENT) is False


def test_security_policy_defaults():
    assert security_policy.default_mode == "read_only"
    assert security_policy.require_approval_for_email_send is True
    assert security_policy.require_approval_for_event_create is True


def test_security_policy_is_frozen():
    policy = SecurityPolicy()
    try:
        policy.default_mode = "write"  # type: ignore[misc]
        assert False, "should have raised"
    except (AttributeError, TypeError):
        pass
