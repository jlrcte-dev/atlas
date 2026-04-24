"""Repository layer — data access for Atlas AI Assistant."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import FinanceDuplicateClosingError, FinanceDuplicateSnapshotError
from app.db.models import (
    Account,
    AccountBalanceSnapshot,
    AuditLog,
    DailyBriefing,
    DraftAction,
    FinancialEntry,
    MonthlyClosing,
    User,
)

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


# ── Finance ───────────────────────────────────────────────────────


class AccountRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, name: str, institution: str = "", is_active: bool = True) -> Account:
        account = Account(name=name, institution=institution, is_active=is_active)
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account

    def get(self, account_id: int) -> Account | None:
        return self.db.get(Account, account_id)

    def get_by_name(self, name: str) -> Account | None:
        """Case-insensitive lookup by account name. Returns None if not found."""
        if not name:
            return None
        return (
            self.db.query(Account)
            .filter(func.lower(Account.name) == name.lower())
            .first()
        )

    def list_all(self) -> list[Account]:
        return self.db.query(Account).order_by(Account.name).all()

    def update(self, account: Account, **kwargs: object) -> Account:
        for key, value in kwargs.items():
            setattr(account, key, value)
        account.updated_at = datetime.now(UTC)
        self.db.add(account)
        self.db.commit()
        self.db.refresh(account)
        return account


class MonthlyClosingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        month_ref: str,
        initial_balance: Decimal,
        notes: str | None = None,
    ) -> MonthlyClosing:
        closing = MonthlyClosing(
            month_ref=month_ref,
            initial_balance=initial_balance,
            notes=notes,
        )
        self.db.add(closing)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise FinanceDuplicateClosingError(month_ref)
        self.db.refresh(closing)
        return closing

    def get(self, closing_id: int) -> MonthlyClosing | None:
        return self.db.get(MonthlyClosing, closing_id)

    def get_by_month(self, month_ref: str) -> MonthlyClosing | None:
        return (
            self.db.query(MonthlyClosing)
            .filter(MonthlyClosing.month_ref == month_ref)
            .first()
        )

    def update(self, closing: MonthlyClosing, **kwargs: object) -> MonthlyClosing:
        for key, value in kwargs.items():
            setattr(closing, key, value)
        closing.updated_at = datetime.now(UTC)
        self.db.add(closing)
        self.db.commit()
        self.db.refresh(closing)
        return closing


class FinancialEntryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        description: str,
        amount: Decimal,
        entry_type: str,
        status: str,
        month_ref: str,
        category: str | None = None,
        due_date: str | None = None,
        settlement_date: str | None = None,
        is_investment: bool = False,
        notes: str | None = None,
    ) -> FinancialEntry:
        entry = FinancialEntry(
            description=description,
            amount=amount,
            type=entry_type,
            status=status,
            month_ref=month_ref,
            category=category,
            due_date=due_date,
            settlement_date=settlement_date,
            is_investment=is_investment,
            notes=notes,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def get(self, entry_id: int) -> FinancialEntry | None:
        return self.db.get(FinancialEntry, entry_id)

    def list_by_month(self, month_ref: str) -> list[FinancialEntry]:
        return (
            self.db.query(FinancialEntry)
            .filter(FinancialEntry.month_ref == month_ref)
            .order_by(FinancialEntry.created_at.desc())
            .all()
        )

    def update(self, entry: FinancialEntry, **kwargs: object) -> FinancialEntry:
        for key, value in kwargs.items():
            setattr(entry, key, value)
        entry.updated_at = datetime.now(UTC)
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def delete(self, entry: FinancialEntry) -> None:
        self.db.delete(entry)
        self.db.commit()


class AccountBalanceSnapshotRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        account_id: int,
        month_ref: str,
        balance: Decimal,
        reference_date: str | None = None,
        notes: str | None = None,
    ) -> AccountBalanceSnapshot:
        snapshot = AccountBalanceSnapshot(
            account_id=account_id,
            month_ref=month_ref,
            balance=balance,
            reference_date=reference_date,
            notes=notes,
        )
        self.db.add(snapshot)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise FinanceDuplicateSnapshotError(account_id, month_ref)
        self.db.refresh(snapshot)
        return snapshot

    def get(self, snapshot_id: int) -> AccountBalanceSnapshot | None:
        return self.db.get(AccountBalanceSnapshot, snapshot_id)

    def get_by_account_month(
        self, account_id: int, month_ref: str
    ) -> AccountBalanceSnapshot | None:
        return (
            self.db.query(AccountBalanceSnapshot)
            .filter(
                AccountBalanceSnapshot.account_id == account_id,
                AccountBalanceSnapshot.month_ref == month_ref,
            )
            .first()
        )

    def list_by_month(self, month_ref: str) -> list[AccountBalanceSnapshot]:
        return (
            self.db.query(AccountBalanceSnapshot)
            .filter(AccountBalanceSnapshot.month_ref == month_ref)
            .all()
        )

    def update(
        self, snapshot: AccountBalanceSnapshot, **kwargs: object
    ) -> AccountBalanceSnapshot:
        for key, value in kwargs.items():
            setattr(snapshot, key, value)
        snapshot.updated_at = datetime.now(UTC)
        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)
        return snapshot
