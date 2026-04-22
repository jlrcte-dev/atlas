"""SQLAlchemy ORM models for Atlas AI Assistant."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    telegram_id: Mapped[str] = mapped_column(String(50), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    preferences: Mapped[UserPreference | None] = relationship(
        back_populates="user",
        uselist=False,
    )
    draft_actions: Mapped[list[DraftAction]] = relationship(back_populates="user")
    briefings: Mapped[list[DailyBriefing]] = relationship(back_populates="user")


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True)
    news_topics: Mapped[str] = mapped_column(Text, default="")
    briefing_time: Mapped[str] = mapped_column(String(20), default="07:00")
    timezone: Mapped[str] = mapped_column(String(80), default="America/Sao_Paulo")

    user: Mapped[User] = relationship(back_populates="preferences")


class DraftAction(Base):
    __tablename__ = "draft_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    type: Mapped[str] = mapped_column(String(50), index=True)
    payload: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User | None] = relationship(back_populates="draft_actions")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action_type: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(30))
    user_id: Mapped[str] = mapped_column(String(50), default="")
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class NewsSource(Base):
    __tablename__ = "news_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(500), unique=True)
    category: Mapped[str] = mapped_column(String(80), default="general")


class DailyBriefing(Base):
    __tablename__ = "daily_briefings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped[User | None] = relationship(back_populates="briefings")


# ── Finance ───────────────────────────────────────────────────────


class Account(Base):
    __tablename__ = "finance_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    institution: Mapped[str] = mapped_column(String(120), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    balance_snapshots: Mapped[list[AccountBalanceSnapshot]] = relationship(
        back_populates="account"
    )


class MonthlyClosing(Base):
    __tablename__ = "finance_monthly_closings"
    __table_args__ = (UniqueConstraint("month_ref", name="uq_finance_closing_month_ref"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    month_ref: Mapped[str] = mapped_column(String(7), unique=True, index=True)
    initial_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class FinancialEntry(Base):
    __tablename__ = "finance_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    description: Mapped[str] = mapped_column(String(300))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    type: Mapped[str] = mapped_column(String(20))       # income | expense
    status: Mapped[str] = mapped_column(String(20))     # settled | pending
    month_ref: Mapped[str] = mapped_column(String(7), index=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    due_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    settlement_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_investment: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class AccountBalanceSnapshot(Base):
    __tablename__ = "finance_account_balance_snapshots"
    __table_args__ = (
        UniqueConstraint("account_id", "month_ref", name="uq_finance_snapshot_account_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("finance_accounts.id"), index=True
    )
    month_ref: Mapped[str] = mapped_column(String(7), index=True)
    balance: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    reference_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    account: Mapped[Account] = relationship(back_populates="balance_snapshots")
