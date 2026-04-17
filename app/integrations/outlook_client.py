"""Outlook / Microsoft 365 email integration (read-only).

Implements the same structural contract as GmailClient (BaseEmailClient):
  - list_recent_emails(max_results)
  - get_email(email_id)

Both return EmailMessage objects — same fields, same semantics.
Uses Microsoft Graph REST API (v1.0) with a bearer token obtained via MSAL.
"""

from __future__ import annotations

import httpx

from app.core.logging import get_logger
from app.integrations.email_models import EmailMessage
from app.integrations.microsoft_auth import get_microsoft_access_token

logger = get_logger("integrations.outlook")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
MESSAGE_FIELDS = "id,subject,bodyPreview,isRead,receivedDateTime,from"
REQUEST_TIMEOUT = 15.0


class OutlookClient:
    def list_recent_emails(self, max_results: int = 10) -> list[EmailMessage]:
        logger.info("list_recent_emails (outlook) max_results=%d", max_results)

        url = f"{GRAPH_BASE}/me/mailFolders/inbox/messages"
        params = {"$top": max_results, "$select": MESSAGE_FIELDS, "$orderby": "receivedDateTime desc"}

        data = self._get(url, params=params)
        messages = data.get("value", [])
        return [self._to_email_message(m) for m in messages]

    def get_email(self, email_id: str) -> EmailMessage | None:
        logger.info("get_email (outlook) id=%s", email_id)

        url = f"{GRAPH_BASE}/me/messages/{email_id}"
        params = {"$select": MESSAGE_FIELDS}

        try:
            data = self._get(url, params=params)
        except httpx.HTTPStatusError as exc:
            logger.warning("Erro ao buscar email Outlook %s: %s", email_id, exc)
            return None

        return self._to_email_message(data)

    def _get(self, url: str, params: dict | None = None) -> dict:
        token = get_microsoft_access_token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        resp = httpx.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def _to_email_message(self, msg: dict) -> EmailMessage:
        msg_id = msg.get("id", "")
        subject = msg.get("subject") or "(sem assunto)"
        snippet = msg.get("bodyPreview") or ""
        timestamp = msg.get("receivedDateTime") or ""
        is_read = bool(msg.get("isRead", False))
        sender = self._format_sender(msg.get("from"))
        priority = self._classify_priority(sender, subject, snippet, is_read)

        return EmailMessage(
            id=msg_id,
            sender=sender,
            subject=subject,
            snippet=snippet,
            priority=priority,
            timestamp=timestamp,
            is_read=is_read,
        )

    @staticmethod
    def _format_sender(from_field: dict | None) -> str:
        if not from_field:
            return ""
        addr = from_field.get("emailAddress") or {}
        name = addr.get("name") or ""
        email = addr.get("address") or ""
        if name and email:
            return f"{name} <{email}>"
        return email or name

    @staticmethod
    def _classify_priority(sender: str, subject: str, snippet: str, is_read: bool) -> str:
        text = f"{sender} {subject} {snippet}".lower()

        high_terms = ("urgente", "reuniao", "reunião", "prazo", "importante")
        medium_terms = ("atualizacao", "atualização", "follow-up", "retorno")

        if not is_read and any(term in text for term in high_terms):
            return "alta"
        if any(term in text for term in medium_terms):
            return "media"
        return "baixa"
