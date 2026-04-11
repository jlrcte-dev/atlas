"""Repository layer — data access for Atlas AI Assistant."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.db.models import AuditLog, DailyBriefing, DraftAction, User

# ── User ──────────────────────────────────────────────────────────


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_telegram_id(self, telegram_id: str) -> User | None:
        return self.db.query(User).filter(User.telegram_id == telegram_id).first()

    def create(self, name: str, telegram_id: str) -> User:
        user = User(name=name, telegram_id=telegram_id)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_or_create(self, name: str, telegram_id: str) -> User:
        user = self.get_by_telegram_id(telegram_id)
        if user:
            return user
        return self.create(name, telegram_id)


# ── DraftAction ───────────────────────────────────────────────────


class DraftActionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        action_type: str,
        payload: dict,
        user_id: int | None = None,
    ) -> DraftAction:
        draft = DraftAction(
            type=action_type,
            payload=json.dumps(payload, ensure_ascii=False),
            status="pending",
            user_id=user_id,
        )
        self.db.add(draft)
        self.db.commit()
        self.db.refresh(draft)
        return draft

    def get(self, draft_id: int) -> DraftAction | None:
        return self.db.get(DraftAction, draft_id)

    def update_status(self, draft: DraftAction, status: str) -> DraftAction:
        draft.status = status
        if status in ("approved", "rejected"):
            draft.resolved_at = datetime.now(UTC)
        self.db.add(draft)
        self.db.commit()
        self.db.refresh(draft)
        return draft

    def list_pending(self, user_id: int | None = None) -> list[DraftAction]:
        query = self.db.query(DraftAction).filter(DraftAction.status == "pending")
        if user_id is not None:
            query = query.filter(DraftAction.user_id == user_id)
        return query.order_by(DraftAction.created_at.desc()).all()

    def list_all(self, limit: int = 50) -> list[DraftAction]:
        return self.db.query(DraftAction).order_by(DraftAction.created_at.desc()).limit(limit).all()


# ── AuditLog ─────────────────────────────────────────────────────


class AuditLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def log(
        self,
        action_type: str,
        status: str,
        user_id: str = "",
        metadata: dict | None = None,
    ) -> AuditLog:
        record = AuditLog(
            action_type=action_type,
            status=status,
            user_id=user_id,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def list_recent(self, limit: int = 50) -> list[AuditLog]:
        return self.db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()


# ── DailyBriefing ────────────────────────────────────────────────


class DailyBriefingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, content: str, user_id: int | None = None) -> DailyBriefing:
        briefing = DailyBriefing(content=content, user_id=user_id)
        self.db.add(briefing)
        self.db.commit()
        self.db.refresh(briefing)
        return briefing

    def get_latest(self) -> DailyBriefing | None:
        return self.db.query(DailyBriefing).order_by(DailyBriefing.created_at.desc()).first()
