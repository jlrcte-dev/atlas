"""Base contract for email provider clients.

Structural interface satisfied by GmailClient and OutlookClient.
Used as a type hint by InboxService — no runtime enforcement.
"""

from __future__ import annotations

from typing import Protocol

from app.integrations.email_models import EmailMessage


class BaseEmailClient(Protocol):
    def list_recent_emails(self, max_results: int = 10) -> list[EmailMessage]: ...

    def get_email(self, email_id: str) -> EmailMessage | None: ...
