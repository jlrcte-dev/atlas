"""Calendar Copilot service.

Retrieves agenda, detects free slots, and prepares event proposals.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.core.logging import get_logger, log_action
from app.integrations.calendar_client import GoogleCalendarClient

logger = get_logger("services.calendar")


class CalendarService:
    WORK_START = "08:00"
    WORK_END = "18:00"

    def __init__(self) -> None:
        self.client = GoogleCalendarClient()

    def get_today_events(self) -> dict:
        """Return today's agenda as structured dict.

        Times are already in local timezone (UTC-3) from the client.
        """
        events = self.client.get_today_events()
        items = [GoogleCalendarClient.to_dict(e) for e in events]
        result = {
            "total": len(events),
            "events": items,
            "summary": f"{len(events)} compromisso(s) hoje.",
        }
        log_action(logger, "get_today_events", total=len(events))
        return result

    def find_free_slots(self, duration_minutes: int = 60) -> list[dict]:
        """Calculate available time windows between timed events during work hours.

        All-day events (birthdays, holidays) are excluded from slot calculation
        since they don't occupy specific time blocks.
        """
        today_data = self.get_today_events()
        # Filter out all-day events — they don't block time slots
        timed_events = [e for e in today_data["events"] if not e.get("all_day")]

        work_start = datetime.strptime(self.WORK_START, "%H:%M")
        work_end = datetime.strptime(self.WORK_END, "%H:%M")

        if not timed_events:
            total = int((work_end - work_start).total_seconds() / 60)
            return [{"start": self.WORK_START, "end": self.WORK_END, "duration_minutes": total}]

        sorted_events = sorted(timed_events, key=lambda e: e["start"])
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
