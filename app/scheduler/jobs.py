from sqlalchemy.orm import Session

from app.modules.briefing.service import BriefingService


def run_daily_briefing_job(db: Session) -> dict:
    return BriefingService(db).run_daily_briefing()
