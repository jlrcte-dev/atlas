"""Daily Briefing service.

Consolidates inbox, calendar, and news into a single executive briefing.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_action
from app.db.repositories import DailyBriefingRepository
from app.modules.briefing.news_service import NewsService
from app.modules.calendar.service import CalendarService
from app.modules.inbox.service import InboxService

logger = get_logger("services.briefing")


class BriefingService:
    def __init__(self, db: Session) -> None:
        self.briefings = DailyBriefingRepository(db)
        self.inbox = InboxService()
        self.calendar = CalendarService()
        self.news = NewsService()

    def run_daily_briefing(self) -> dict:
        """Generate, persist, and return the daily briefing."""
        inbox_data = self.inbox.summarize_emails()
        calendar_data = self.calendar.get_today_events()
        news_data = self.news.summarize_news()
        free_slots = self.calendar.find_free_slots()

        content = self._compose(inbox_data, calendar_data, news_data, free_slots)
        saved = self.briefings.create(content)

        log_action(logger, "run_daily_briefing", briefing_id=saved.id)

        return {
            "id": saved.id,
            "content": content,
            "sections": {
                "inbox": inbox_data,
                "calendar": calendar_data,
                "news": news_data,
                "free_slots": free_slots,
            },
        }

    @staticmethod
    def _compose(
        inbox: dict,
        calendar: dict,
        news: dict,
        free_slots: list[dict],
    ) -> str:
        lines: list[str] = [
            "BRIEFING DIARIO",
            "=" * 30,
            "",
            f"AGENDA — {calendar['total']} compromisso(s)",
        ]
        for evt in calendar.get("events", []):
            lines.append(f"  - {evt['start']} | {evt['title']}")

        if free_slots:
            lines.append(f"\nHORARIOS LIVRES — {len(free_slots)} slot(s)")
            for slot in free_slots:
                lines.append(f"  - {slot['start']}-{slot['end']} ({slot['duration_minutes']}min)")

        lines.append(f"\nINBOX — {inbox['summary']}")
        for item in inbox.get("top5", []):
            lines.append(f"  * {item['sender']}: {item['subject']}")

        lines.append(f"\nNOTICIAS — {news['summary']}")
        for item in news.get("items", [])[:3]:
            lines.append(f"  - {item['title']}")

        return "\n".join(lines)
