"""Gmail integration client (MCP-ready stub).

Returns mock data. Replace method bodies with real Google Workspace
MCP calls when connecting to production.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from app.core.logging import get_logger

logger = get_logger("integrations.gmail")


@dataclass
class EmailMessage:
    id: str
    sender: str
    subject: str
    snippet: str
    priority: str  # alta | media | baixa
    timestamp: str
    is_read: bool


class GmailClient:
    """Gmail adapter. All methods return mock data until MCP wiring."""

    def list_recent_emails(self, max_results: int = 10) -> list[EmailMessage]:
        logger.info("list_recent_emails (stub) max_results=%d", max_results)
        return [
            EmailMessage(
                id="msg_001",
                sender="cliente@empresa.com",
                subject="Reuniao pendente",
                snippet="Precisamos alinhar o escopo do projeto ate sexta.",
                priority="alta",
                timestamp="2026-04-10T08:30:00",
                is_read=False,
            ),
            EmailMessage(
                id="msg_002",
                sender="rh@empresa.com",
                subject="Atualizacao de beneficios",
                snippet="Novos beneficios a partir de maio.",
                priority="media",
                timestamp="2026-04-10T07:15:00",
                is_read=True,
            ),
            EmailMessage(
                id="msg_003",
                sender="newsletter@mercado.com",
                subject="Resumo macro do dia",
                snippet="Ibovespa fecha em alta de 1.2%.",
                priority="baixa",
                timestamp="2026-04-10T06:00:00",
                is_read=True,
            ),
        ][:max_results]

    def get_email(self, email_id: str) -> EmailMessage | None:
        logger.info("get_email (stub) id=%s", email_id)
        emails = {e.id: e for e in self.list_recent_emails()}
        return emails.get(email_id)

    def send_email(self, to: str, subject: str, body: str) -> dict:
        """Execute email send. Must only be called AFTER approval."""
        logger.info("send_email (stub) to=%s subject=%s", to, subject)
        return {"status": "sent", "message_id": "mock_sent_001"}

    @staticmethod
    def to_dict(email: EmailMessage) -> dict:
        return asdict(email)
