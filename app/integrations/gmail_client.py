"""Gmail integration client"""


from __future__ import annotations

from email.utils import parsedate_to_datetime

from googleapiclient.discovery import build

from app.core.logging import get_logger
from app.integrations.email_models import EmailMessage
from app.integrations.google_auth import get_google_credentials

logger = get_logger("integrations.gmail")

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailClient:
    def __init__(self) -> None:
        creds = get_google_credentials(SCOPES)
        self.service = build("gmail", "v1", credentials=creds)

    def list_recent_emails(self, max_results: int = 10) -> list[EmailMessage]:
        logger.info("list_recent_emails (real) max_results=%d", max_results)

        response = (
            self.service.users()
            .messages()
            .list(userId="me", maxResults=max_results, labelIds=["INBOX"])
            .execute()
        )

        messages = response.get("messages", [])
        results: list[EmailMessage] = []

        for msg in messages:
            msg_id = msg["id"]

            full_msg = (
                self.service.users()
                .messages()
                .get(
                    userId="me",
                    id=msg_id,
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                )
                .execute()
            )

            headers = {
                h["name"]: h["value"]
                for h in full_msg.get("payload", {}).get("headers", [])
            }

            sender = headers.get("From", "")
            subject = headers.get("Subject", "(sem assunto)")
            date_raw = headers.get("Date", "")
            snippet = full_msg.get("snippet", "")
            label_ids = full_msg.get("labelIds", [])

            is_read = "UNREAD" not in label_ids
            priority = self._classify_priority(sender, subject, snippet, is_read)
            timestamp = self._normalize_date(date_raw)

            results.append(
                EmailMessage(
                    id=msg_id,
                    sender=sender,
                    subject=subject,
                    snippet=snippet,
                    priority=priority,
                    timestamp=timestamp,
                    is_read=is_read,
                )
            )

        return results

    def get_email(self, email_id: str) -> EmailMessage | None:
        logger.info("get_email (real) id=%s", email_id)

        try:
            full_msg = (
                self.service.users()
                .messages()
                .get(
                    userId="me",
                    id=email_id,
                    format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                )
                .execute()
            )
        except Exception as exc:
            logger.warning("Erro ao buscar email %s: %s", email_id, exc)
            return None

        headers = {
            h["name"]: h["value"]
            for h in full_msg.get("payload", {}).get("headers", [])
        }

        sender = headers.get("From", "")
        subject = headers.get("Subject", "(sem assunto)")
        date_raw = headers.get("Date", "")
        snippet = full_msg.get("snippet", "")
        label_ids = full_msg.get("labelIds", [])

        is_read = "UNREAD" not in label_ids
        priority = self._classify_priority(sender, subject, snippet, is_read)
        timestamp = self._normalize_date(date_raw)

        return EmailMessage(
            id=email_id,
            sender=sender,
            subject=subject,
            snippet=snippet,
            priority=priority,
            timestamp=timestamp,
            is_read=is_read,
        )

    def send_email(self, to: str, subject: str, body: str) -> dict:
        raise NotImplementedError(
            "Envio de email ainda não implementado. Nesta fase, apenas leitura do Gmail."
        )

    def _classify_priority(
        self, sender: str, subject: str, snippet: str, is_read: bool
    ) -> str:
        text = f"{sender} {subject} {snippet}".lower()

        high_terms = ["urgente", "reunião", "reuniao", "prazo", "importante"]
        medium_terms = ["atualização", "atualizacao", "follow-up", "retorno"]

        if not is_read and any(term in text for term in high_terms):
            return "alta"

        if any(term in text for term in medium_terms):
            return "media"

        return "baixa"

    def _normalize_date(self, date_raw: str) -> str:
        if not date_raw:
            return ""

        try:
            dt = parsedate_to_datetime(date_raw)
            return dt.isoformat()
        except Exception:
            return date_raw