"""Calendar Copilot service.

Retrieves agenda, detects free slots, and prepares event proposals.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.logging import get_logger, log_action
from app.integrations.calendar_client import GoogleCalendarClient

logger = get_logger("services.calendar")

# UTC-3 offset used throughout the service (America/Sao_Paulo standard offset).
# When DST is relevant, replace with zoneinfo.ZoneInfo(settings.timezone).
TZ_BRT = timezone(timedelta(hours=-3))


def _to_local_time(dt_value: str) -> str:
    """Convert an ISO datetime string (UTC or offset-aware) to local HH:MM (UTC-3).

    Handles two formats returned by Google Calendar API:
      - Full ISO with offset:  "2025-04-11T12:00:00Z" or "2025-04-11T12:00:00+00:00"
      - Time-only HH:MM (stub / already local): returned as-is.
    """
    if len(dt_value) <= 5:
        # Already HH:MM — stub data, no conversion needed
        return dt_value

    # Normalise 'Z' suffix to '+00:00' for fromisoformat compatibility (Python 3.11+)
    iso = dt_value.replace("Z", "+00:00")
    try:
        dt_utc = datetime.fromisoformat(iso)
        dt_local = dt_utc.astimezone(TZ_BRT)
        return dt_local.strftime("%H:%M")
    except ValueError:
        # Unexpected format — log and return as-is to avoid data loss
        logger.warning("Unrecognised datetime format from calendar: %r", dt_value)
        return dt_value


class CalendarService:
    WORK_START = "08:00"
    WORK_END = "18:00"

    def __init__(self) -> None:
        self.client = GoogleCalendarClient()

    def get_today_events(self) -> dict:
        """Return today's agenda as structured dict with times in UTC-3."""
        events = self.client.get_today_events()
        items = []
        for e in events:
            d = GoogleCalendarClient.to_dict(e)
            d["start"] = _to_local_time(d["start"])
            d["end"] = _to_local_time(d["end"])
            items.append(d)
        result = {
            "total": len(events),
            "events": items,
            "summary": f"{len(events)} compromisso(s) hoje.",
        }
        log_action(logger, "get_today_events", total=len(events))
        return result

    def find_free_slots(self, duration_minutes: int = 60) -> list[dict]:
        """Calculate available time windows between events during work hours.

        Uses already-converted (UTC-3) times from get_today_events so that
        free-slot calculation is always consistent with displayed event times.
        """
        today_data = self.get_today_events()
        events = today_data["events"]  # list[dict] with start/end already in UTC-3 HH:MM

        work_start = datetime.strptime(self.WORK_START, "%H:%M")
        work_end = datetime.strptime(self.WORK_END, "%H:%M")

        if not events:
            total = int((work_end - work_start).total_seconds() / 60)
            return [{"start": self.WORK_START, "end": self.WORK_END, "duration_minutes": total}]

        sorted_events = sorted(events, key=lambda e: e["start"])
        free_slots: list[dict] = []
        current = work_start

        for event in sorted_events:
            evt_start = datetime.strptime(event["start"][:5], "%H:%M")
            evt_end = (
                datetime.strptime(event["end"][:5], "%H:%M")
                if event.get("end")
                else evt_start + timedelta(hours=1)
            )

            if evt_start > current:
                gap = int((evt_start - current).total_seconds() / 60)
                if gap >= duration_minutes:
                    free_slots.append(
                        {
                            "start": current.strftime("%H:%M"),
                            "end": evt_start.strftime("%H:%M"),
                            "duration_minutes": gap,
                        }
                    )

            current = max(current, evt_end)

        if current < work_end:
            gap = int((work_end - current).total_seconds() / 60)
            if gap >= duration_minutes:
                free_slots.append(
                    {
                        "start": current.strftime("%H:%M"),
                        "end": work_end.strftime("%H:%M"),
                        "duration_minutes": gap,
                    }
                )

        log_action(
            logger,
            "find_free_slots",
            duration_minutes=duration_minutes,
            slots_found=len(free_slots),
        )
        return free_slots

    def propose_event(
        self,
        title: str,
        start: str,
        end: str,
        attendees: list[str] | None = None,
        location: str | None = None,
    ) -> dict:
        """Build a proposal payload (not persisted — goes through approval)."""
        return {
            "title": title,
            "start": start,
            "end": end,
            "attendees": attendees or [],
            "location": location,
            "status": "proposal_ready",
        }

    # Backward compatibility alias
    def get_today_agenda(self) -> dict:
        return self.get_today_events()
