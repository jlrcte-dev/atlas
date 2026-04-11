"""Inbox Copilot service.

Reads, classifies, and summarizes emails via the Gmail integration client.
"""

from __future__ import annotations

from app.core.logging import get_logger, log_action
from app.integrations.gmail_client import GmailClient

logger = get_logger("services.inbox")


class InboxService:
    def __init__(self) -> None:
        self.client = GmailClient()

    def get_recent_emails(self, max_results: int = 10) -> list[dict]:
        """Return raw email list as dicts."""
        emails = self.client.list_recent_emails(max_results)
        log_action(logger, "get_recent_emails", total=len(emails))
        return [GmailClient.to_dict(e) for e in emails]

    def summarize_emails(self) -> dict:
        """Classify and summarize inbox with priority breakdown."""
        emails = self.client.list_recent_emails()
        high = [e for e in emails if e.priority == "alta"]
        medium = [e for e in emails if e.priority == "media"]
        low = [e for e in emails if e.priority == "baixa"]
        unread = [e for e in emails if not e.is_read]

        result = {
            "total": len(emails),
            "high_priority": len(high),
            "medium_priority": len(medium),
            "low_priority": len(low),
            "unread": len(unread),
            "items": [GmailClient.to_dict(e) for e in emails],
            "action_items": [GmailClient.to_dict(e) for e in high],
            "summary": (
                f"{len(emails)} emails — {len(high)} prioritario(s), {len(unread)} nao lido(s)."
            ),
        }
        log_action(
            logger,
            "summarize_emails",
            total=result["total"],
            high_priority=result["high_priority"],
            unread=result["unread"],
        )
        return result

    # Backward compatibility alias
    def get_summary(self) -> dict:
        return self.summarize_emails()
