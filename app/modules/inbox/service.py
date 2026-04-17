"""Inbox Copilot service.

Reads, classifies, and summarizes emails via the Gmail integration client.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger, log_action
from app.integrations.base_email_client import BaseEmailClient
from app.integrations.email_models import email_to_dict
from app.integrations.gmail_client import GmailClient

logger = get_logger("services.inbox")


def _build_default_client() -> BaseEmailClient:
    provider = settings.email_provider.lower()
    if provider == "gmail":
        return GmailClient()
    if provider == "outlook":
        from app.integrations.outlook_client import OutlookClient

        return OutlookClient()
    raise NotImplementedError(f"Email provider nao suportado: {provider}")


class InboxService:
    def __init__(self, client: BaseEmailClient | None = None) -> None:
        self.client = client if client is not None else _build_default_client()

    def get_recent_emails(self, max_results: int = 10) -> list[dict]:
        """Return raw email list as dicts."""
        try:
            emails = self.client.list_recent_emails(max_results)
        except Exception as exc:
            logger.error("Falha ao buscar emails: %s", exc, exc_info=True)
            return []
        log_action(logger, "get_recent_emails", total=len(emails))
        return [email_to_dict(e) for e in emails]

    def summarize_emails(self) -> dict:
        """Classify and summarize inbox with priority breakdown."""
        try:
            emails = self.client.list_recent_emails()
        except Exception as exc:
            logger.error("Falha ao buscar emails: %s", exc, exc_info=True)
            return {
                "total": 0,
                "high_priority": 0,
                "medium_priority": 0,
                "low_priority": 0,
                "unread": 0,
                "items": [],
                "action_items": [],
                "summary": "Inbox temporariamente indisponivel.",
            }
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
            "items": [email_to_dict(e) for e in emails],
            "action_items": [email_to_dict(e) for e in high],
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
