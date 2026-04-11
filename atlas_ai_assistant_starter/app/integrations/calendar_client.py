"""Google Calendar integration client (MCP-ready stub).

Returns mock data. Replace method bodies with real Google Workspace
MCP calls when connecting to production.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from app.core.logging import get_logger

logger = get_logger("integrations.calendar")


@dataclass
class CalendarEvent:
    id: str
    title: str
    start: str  # HH:MM or ISO datetime
    end: str
    location: str | None = None
    attendees: list[str] = field(default_factory=list)


class GoogleCalendarClient:
    """Google Calendar adapter. Returns mock data until MCP wiring."""

    def get_today_events(self) -> list[CalendarEvent]:
        logger.info("get_today_events (stub)")
        return [
            CalendarEvent(
                id="evt_001",
                title="Call com equipe",
                start="09:00",
                end="10:00",
                location="Google Meet",
                attendees=["equipe@empresa.com"],
            ),
            CalendarEvent(
                id="evt_002",
                title="Almoco",
                start="12:00",
                end="13:00",
            ),
            CalendarEvent(
                id="evt_003",
                title="Revisao semanal",
                start="15:00",
                end="16:00",
                location="Escritorio",
                attendees=["gestor@empresa.com"],
            ),
        ]

    def get_events_range(self, start_date: str, end_date: str) -> list[CalendarEvent]:
        logger.info("get_events_range (stub) %s to %s", start_date, end_date)
        return self.get_today_events()

    def create_event(
        self,
        title: str,
        start: str,
        end: str,
        location: str | None = None,
        attendees: list[str] | None = None,
    ) -> dict:
        """Execute event creation. Must only be called AFTER approval."""
        logger.info("create_event (stub) title=%s", title)
        return {"status": "created", "event_id": "mock_evt_new_001"}

    @staticmethod
    def to_dict(event: CalendarEvent) -> dict:
        return asdict(event)
