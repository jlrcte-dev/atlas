"""Policy engine — determines which actions require human approval."""

from __future__ import annotations

from app.core.permissions import ActionType
from app.core.security import security_policy

# Static permission map (fallback when security_policy flags are not set)
_APPROVAL_REQUIRED: dict[ActionType, bool] = {
    ActionType.READ_EMAILS: False,
    ActionType.DRAFT_EMAIL: False,
    ActionType.SEND_EMAIL: True,
    ActionType.READ_CALENDAR: False,
    ActionType.CREATE_EVENT: True,
    ActionType.READ_NEWS: False,
    ActionType.GENERATE_BRIEFING: False,
}


def requires_approval(action_type: ActionType) -> bool:
    """Check whether an action type needs explicit human confirmation."""
    if action_type == ActionType.SEND_EMAIL:
        return security_policy.require_approval_for_email_send
    if action_type == ActionType.CREATE_EVENT:
        return security_policy.require_approval_for_event_create
    return _APPROVAL_REQUIRED.get(action_type, False)


def is_read_only(action_type: ActionType) -> bool:
    """Return True if the action is strictly read-only (no side effects)."""
    return action_type in (
        ActionType.READ_EMAILS,
        ActionType.READ_CALENDAR,
        ActionType.READ_NEWS,
        ActionType.GENERATE_BRIEFING,
    )
