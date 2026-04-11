from sqlalchemy.orm import Session

from app.services.briefing_service import BriefingService


def run_daily_briefing_job(db: Session) -> dict:
    return BriefingService(db).run_daily_briefing()
