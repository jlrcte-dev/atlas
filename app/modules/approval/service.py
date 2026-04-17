"""Approval system service.

Gates all write operations behind human confirmation.
Every state transition is recorded in the audit log.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import ActionAlreadyResolvedError
from app.core.logging import get_logger, log_action
from app.db.models import DraftAction
from app.db.repositories import AuditLogRepository, DraftActionRepository

logger = get_logger("services.approval")


class ApprovalService:
    def __init__(self, db: Session) -> None:
        self.drafts = DraftActionRepository(db)
        self.audit = AuditLogRepository(db)

    # ── Queries ───────────────────────────────────────────────────

    def get_draft(self, draft_id: int) -> DraftAction | None:
        return self.drafts.get(draft_id)

    def list_pending(self) -> list[DraftAction]:
        return self.drafts.list_pending()

    # ── Draft creation ────────────────────────────────────────────

    def create_email_draft(self, payload: dict, user_id: str = "") -> DraftAction:
        draft = self.drafts.create("draft_email", payload)
        self.audit.log("draft_email", "pending", user_id=user_id, metadata={"draft_id": draft.id})
        log_action(logger, "create_email_draft", user_id=user_id, draft_id=draft.id)
        return draft

    def create_event_proposal(self, payload: dict, user_id: str = "") -> DraftAction:
        draft = self.drafts.create("create_event", payload)
        self.audit.log("create_event", "pending", user_id=user_id, metadata={"draft_id": draft.id})
        log_action(logger, "create_event_proposal", user_id=user_id, draft_id=draft.id)
        return draft

    # ── Resolution ────────────────────────────────────────────────

    def confirm(self, draft: DraftAction, user_id: str = "") -> DraftAction:
        """Approve a pending action. Raises if already resolved."""
        if draft.status != "pending":
            raise ActionAlreadyResolvedError(draft.id, draft.status)

        updated = self.drafts.update_status(draft, "approved")
        self.audit.log(draft.type, "approved", user_id=user_id, metadata={"draft_id": draft.id})
        log_action(logger, "confirm", user_id=user_id, draft_id=draft.id, type=draft.type)
        return updated

    def reject(self, draft: DraftAction, user_id: str = "") -> DraftAction:
        """Reject a pending action. Raises if already resolved."""
        if draft.status != "pending":
            raise ActionAlreadyResolvedError(draft.id, draft.status)

        updated = self.drafts.update_status(draft, "rejected")
        self.audit.log(draft.type, "rejected", user_id=user_id, metadata={"draft_id": draft.id})
        log_action(logger, "reject", user_id=user_id, draft_id=draft.id, type=draft.type)
        return updated
