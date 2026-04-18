"""Inbox Copilot service.

Reads, classifies, and summarizes emails via the active email provider client.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger, log_action
from app.integrations.base_email_client import BaseEmailClient
from app.integrations.email_classifier import EmailClassification, classify_email
from app.integrations.email_models import EmailMessage, email_to_dict
from app.integrations.gmail_client import GmailClient

logger = get_logger("services.inbox")

_FALLBACK_CLASSIFICATION = EmailClassification(
    category="update",
    priority="baixa",
    requires_response=False,
    has_deadline=False,
    is_follow_up=False,
    is_opportunity=False,
    reason_codes=["classification_error"],
    score=0,
    score_reasons=[],
)


def _build_default_client() -> BaseEmailClient:
    provider = settings.email_provider.lower()
    if provider == "gmail":
        return GmailClient()
    if provider == "outlook":
        from app.integrations.outlook_client import OutlookClient

        return OutlookClient()
    raise NotImplementedError(f"Email provider nao suportado: {provider}")


def _classify_all(emails: list[EmailMessage]) -> dict[str, EmailClassification]:
    """Classify each email and mutate email.priority in place.

    InboxService is the authoritative source of classification.
    Any priority set by the client is overwritten here.
    Per-email errors are caught and logged — a single failure never aborts the summary.
    """
    result: dict[str, EmailClassification] = {}
    for email in emails:
        try:
            clf = classify_email(email)
            email.priority = clf.priority  # service is the source of truth
            result[email.id] = clf
        except Exception as exc:
            logger.warning("Falha ao classificar email %s: %s", email.id, exc)
            email.priority = "baixa"
            result[email.id] = _FALLBACK_CLASSIFICATION
    return result


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
        """Classify and summarize inbox with priority breakdown and operational flags."""
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

        classifications = _classify_all(emails)

        high = [e for e in emails if classifications[e.id].priority == "alta"]
        medium = [e for e in emails if classifications[e.id].priority == "media"]
        low = [e for e in emails if classifications[e.id].priority == "baixa"]
        unread = [e for e in emails if not e.is_read]

        # action_items: emails with any operational flag, ordered by score descending
        action_emails = sorted(
            [
                e for e in emails
                if (
                    classifications[e.id].requires_response
                    or classifications[e.id].has_deadline
                    or classifications[e.id].is_follow_up
                    or classifications[e.id].is_opportunity
                )
            ],
            key=lambda e: -classifications[e.id].score,
        )

        summary = _build_summary(emails, classifications, unread)

        result = {
            "total": len(emails),
            "high_priority": len(high),
            "medium_priority": len(medium),
            "low_priority": len(low),
            "unread": len(unread),
            "items": [email_to_dict(e) for e in emails],
            "action_items": [email_to_dict(e) for e in action_emails],
            "summary": summary,
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


def _build_summary(
    emails: list[EmailMessage],
    classifications: dict[str, EmailClassification],
    unread: list[EmailMessage],
) -> str:
    n_need_action = sum(
        1 for e in emails
        if classifications[e.id].requires_response or classifications[e.id].has_deadline
    )
    # follow-ups not already counted in need_action (avoid double counting)
    n_follow_up = sum(
        1 for e in emails
        if classifications[e.id].is_follow_up
        and not (classifications[e.id].requires_response or classifications[e.id].has_deadline)
    )
    n_newsletter = sum(1 for e in emails if classifications[e.id].category == "newsletter")
    n_noise = sum(1 for e in emails if classifications[e.id].category == "noise")

    parts = [f"{len(emails)} email(s)"]
    if n_need_action:
        parts.append(f"{n_need_action} exige(m) ação")
    if n_follow_up:
        parts.append(f"{n_follow_up} follow-up(s)")
    if n_newsletter:
        parts.append(f"{n_newsletter} newsletter(s)")
    if n_noise:
        parts.append(f"{n_noise} ruído(s)")
    if unread:
        parts.append(f"{len(unread)} não lido(s)")

    return " — ".join(parts) + "."
