"""Pydantic schemas for the Finance module."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

_MONTH_REF_RE = re.compile(r"^\d{4}-\d{2}$")


def _check_month_ref(v: str) -> str:
    if not _MONTH_REF_RE.match(v):
        raise ValueError(f"month_ref inválido: '{v}'. Use YYYY-MM.")
    return v


# ── Account ───────────────────────────────────────────────────────


class AccountCreate(BaseModel):
    name: str
    institution: str = ""
    is_active: bool = True


class AccountUpdate(BaseModel):
    name: str | None = None
    institution: str | None = None
    is_active: bool | None = None


class AccountResponse(BaseModel):
    id: int
    name: str
    institution: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── MonthlyClosing ────────────────────────────────────────────────


class MonthlyClosingCreate(BaseModel):
    month_ref: str
    initial_balance: Decimal
    notes: str | None = None

    @field_validator("month_ref")
    @classmethod
    def validate_month_ref(cls, v: str) -> str:
        return _check_month_ref(v)


class MonthlyClosingUpdate(BaseModel):
    initial_balance: Decimal | None = None
    notes: str | None = None


class MonthlyClosingResponse(BaseModel):
    id: int
    month_ref: str
    initial_balance: Decimal
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── FinancialEntry ────────────────────────────────────────────────

_VALID_TYPES = frozenset({"income", "expense"})
_VALID_STATUSES = frozenset({"settled", "pending"})


class FinancialEntryCreate(BaseModel):
    description: str
    amount: Decimal
    type: str
    status: str
    month_ref: str
    category: str | None = None
    due_date: str | None = None
    settlement_date: str | None = None
    is_investment: bool = False
    notes: str | None = None

    @field_validator("month_ref")
    @classmethod
    def validate_month_ref(cls, v: str) -> str:
        return _check_month_ref(v)

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in _VALID_TYPES:
            raise ValueError("type deve ser 'income' ou 'expense'")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in _VALID_STATUSES:
            raise ValueError("status deve ser 'settled' ou 'pending'")
        return v


class FinancialEntryUpdate(BaseModel):
    description: str | None = None
    amount: Decimal | None = None
    type: str | None = None
    status: str | None = None
    category: str | None = None
    due_date: str | None = None
    settlement_date: str | None = None
    is_investment: bool | None = None
    notes: str | None = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_TYPES:
            raise ValueError("type deve ser 'income' ou 'expense'")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_STATUSES:
            raise ValueError("status deve ser 'settled' ou 'pending'")
        return v


class FinancialEntryResponse(BaseModel):
    id: int
    description: str
    amount: Decimal
    type: str
    status: str
    month_ref: str
    category: str | None
    due_date: str | None
    settlement_date: str | None
    is_investment: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── AccountBalanceSnapshot ────────────────────────────────────────


class AccountBalanceSnapshotCreate(BaseModel):
    account_id: int
    month_ref: str
    balance: Decimal
    reference_date: str | None = None
    notes: str | None = None

    @field_validator("month_ref")
    @classmethod
    def validate_month_ref(cls, v: str) -> str:
        return _check_month_ref(v)


class AccountBalanceSnapshotUpdate(BaseModel):
    balance: Decimal | None = None
    reference_date: str | None = None
    notes: str | None = None


class AccountBalanceSnapshotResponse(BaseModel):
    id: int
    account_id: int
    month_ref: str
    balance: Decimal
    reference_date: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Monthly Summary ───────────────────────────────────────────────


class AccountSummary(BaseModel):
    account_id: int
    account_name: str
    institution: str
    balance: Decimal


class MonthlySummaryResponse(BaseModel):
    month_ref: str
    initial_balance: Decimal
    expenses_paid: Decimal
    expenses_pending: Decimal
    income_received: Decimal
    income_pending: Decimal
    current_balance: Decimal
    projected_final_balance: Decimal
    conference_total: Decimal
    conference_difference: Decimal
    accounts: list[AccountSummary]
