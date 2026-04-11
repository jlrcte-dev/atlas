"""Google Calendar integration client.

Uses Google Calendar API v3 with OAuth 2.0 via shared google_auth module.

Setup:
  1. Download OAuth credentials from Google Cloud Console
     (APIs & Services > Credentials > OAuth 2.0 Client IDs > Desktop app)
  2. Save to credentials/google_oauth_credentials.json
  3. On first run, browser opens for authorization.
     Token is saved to credentials/google_token.json automatically.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.logging import get_logger
from app.integrations.google_auth import get_google_credentials

logger = get_logger("integrations.calendar")

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

# Timezone offset from settings (America/Sao_Paulo = UTC-3 standard)
_TZ_OFFSET = timezone(timedelta(hours=-3))


@dataclass
class CalendarEvent:
    id: str
    title: str
    start: str  # HH:MM for timed events, YYYY-MM-DD for all-day
    end: str
    all_day: bool = False
    location: str | None = None
    attendees: list[str] = field(default_factory=list)


def _build_service():
    """Build authenticated Google Calendar service using shared auth."""
    from googleapiclient.discovery import build

    creds = get_google_credentials(SCOPES)
    return build("calendar", "v3", credentials=creds)


def _parse_event_time(dt_obj: dict) -> tuple[str, bool]:
    """Parse a Google Calendar start/end object.

    Returns (formatted_time, is_all_day):
      - Timed events: ("HH:MM", False) — converted to local timezone
      - All-day events: ("YYYY-MM-DD", True)
    """
    if "dateTime" in dt_obj:
        dt = datetime.fromisoformat(dt_obj["dateTime"])
        local_dt = dt.astimezone(_TZ_OFFSET)
        return local_dt.strftime("%H:%M"), False

    # All-day event: Google returns {"date": "2026-04-11"}
    if "date" in dt_obj:
        return dt_obj["date"], True

    return "00:00", False


class GoogleCalendarClient:
    """Adapter for Google Calendar API v3."""

    def __init__(self) -> None:
        self._service = None  # lazy init

    def _get_service(self):
        if self._service is None:
            self._service = _build_service()
        return self._service

    def get_today_events(self) -> list[CalendarEvent]:
        """Return today's events from the configured calendar."""
        try:
            now = datetime.now(tz=timezone.utc)
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)
            return self._fetch_events(
                time_min=start_of_day.isoformat(),
                time_max=end_of_day.isoformat(),
            )
        except Exception:
            logger.exception("get_today_events failed")
            return []

    def get_events_range(self, start_date: str, end_date: str) -> list[CalendarEvent]:
        """Return events between two dates (ISO 8601 or YYYY-MM-DD)."""
        try:
            if "T" not in start_date:
                start_date = f"{start_date}T00:00:00Z"
            if "T" not in end_date:
                end_date = f"{end_date}T23:59:59Z"
            logger.info("get_events_range %s to %s", start_date, end_date)
            return self._fetch_events(time_min=start_date, time_max=end_date)
        except Exception:
            logger.exception("get_events_range failed")
            return []

    def _fetch_events(self, time_min: str, time_max: str) -> list[CalendarEvent]:
        """Execute API call and convert to CalendarEvent list."""
        service = self._get_service()
        calendar_id = settings.google_calendar_id

        result = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events: list[CalendarEvent] = []
        for item in result.get("items", []):
            start_str, start_all_day = _parse_event_time(item.get("start", {}))
            end_str, _ = _parse_event_time(item.get("end", {}))

            attendees_raw = item.get("attendees", [])
            attendees = [a["email"] for a in attendees_raw if a.get("email")]

            events.append(
                CalendarEvent(
                    id=item.get("id", ""),
                    title=item.get("summary", "(sem titulo)"),
                    start=start_str,
                    end=end_str,
                    all_day=start_all_day,
                    location=item.get("location"),
                    attendees=attendees,
                )
            )

        logger.info("_fetch_events: %d event(s) found", len(events))
        return events

    def create_event(
        self,
        title: str,
        start: str,
        end: str,
        location: str | None = None,
        attendees: list[str] | None = None,
    ) -> dict:
        """Create event on Google Calendar. Must only be called after approval."""
        try:
            service = self._get_service()
            calendar_id = settings.google_calendar_id
            today = datetime.now().strftime("%Y-%m-%d")
            timezone_id = settings.timezone

            def _to_iso(time_str: str) -> str:
                if "T" in time_str:
                    return time_str
                return f"{today}T{time_str}:00"

            event_body: dict = {
                "summary": title,
                "start": {"dateTime": _to_iso(start), "timeZone": timezone_id},
                "end": {"dateTime": _to_iso(end), "timeZone": timezone_id},
            }
            if location:
                event_body["location"] = location
            if attendees:
                event_body["attendees"] = [{"email": e} for e in attendees]

            created = (
                service.events()
                .insert(calendarId=calendar_id, body=event_body)
                .execute()
            )
            event_id = created.get("id", "")
            logger.info("create_event: id=%s title=%s", event_id, title)
            return {"status": "created", "event_id": event_id}
        except Exception:
            logger.exception("create_event failed: title=%s", title)
            return {"status": "error", "event_id": ""}

    @staticmethod
    def to_dict(event: CalendarEvent) -> dict:
        return asdict(event)
