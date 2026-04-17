"""Shared email domain model.

Provider-agnostic representation of a single email message.
Used by GmailClient, OutlookClient, and InboxService.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class EmailMessage:
    id: str
    sender: str
    subject: str
    snippet: str
    priority: str  # alta | media | baixa
    timestamp: str
    is_read: bool


def email_to_dict(email: EmailMessage) -> dict:
    return asdict(email)
