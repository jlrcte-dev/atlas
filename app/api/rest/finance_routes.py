"""Finance API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.finance.schemas import (
    AccountBalanceSnapshotCreate,
    AccountBalanceSnapshotResponse,
    AccountBalanceSnapshotUpdate,
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    FinancialEntryCreate,
    FinancialEntryResponse,
    FinancialEntryUpdate,
    MonthlyClosingCreate,
    MonthlyClosingResponse,
    MonthlyClosingUpdate,
    MonthlySummaryResponse,
)
from app.modules.finance.service import FinanceService

finance_router = APIRouter(prefix="/finance", tags=["finance"])


def _svc(db: Session = Depends(get_db)) -> FinanceService:
    return FinanceService(db)


# ── Accounts ──────────────────────────────────────────────────────


@finance_router.get("/accounts", response_model=list[AccountResponse])
def list_accounts(svc: FinanceService = Depends(_svc)) -> list[AccountResponse]:
    return svc.list_accounts()


@finance_router.post("/accounts", response_model=AccountResponse, status_code=201)
def create_account(
    payload: AccountCreate,
    svc: FinanceService = Depends(_svc),
) -> AccountResponse:
    return svc.create_account(payload)


@finance_router.patch("/accounts/{account_id}", response_model=AccountResponse)
def update_account(
    account_id: int,
    payload: AccountUpdate,
    svc: FinanceService = Depends(_svc),
) -> AccountResponse:
    return svc.update_account(account_id, payload)


# ── Monthly Closing ───────────────────────────────────────────────


@finance_router.get("/monthly-closing", response_model=MonthlyClosingResponse)
def get_monthly_closing(
    month: str,
    svc: FinanceService = Depends(_svc),
) -> MonthlyClosingResponse:
    return svc.get_monthly_closing(month)


@finance_router.post("/monthly-closing", response_model=MonthlyClosingResponse, status_code=201)
def create_monthly_closing(
    payload: MonthlyClosingCreate,
    svc: FinanceService = Depends(_svc),
) -> MonthlyClosingResponse:
    return svc.create_monthly_closing(payload)


@finance_router.patch("/monthly-closing/{closing_id}", response_model=MonthlyClosingResponse)
def update_monthly_closing(
    closing_id: int,
    payload: MonthlyClosingUpdate,
    svc: FinanceService = Depends(_svc),
) -> MonthlyClosingResponse:
    return svc.update_monthly_closing(closing_id, payload)


# ── Entries ───────────────────────────────────────────────────────


@finance_router.get("/entries", response_model=list[FinancialEntryResponse])
def list_entries(
    month: str,
    svc: FinanceService = Depends(_svc),
) -> list[FinancialEntryResponse]:
    return svc.list_entries(month)


@finance_router.post("/entries", response_model=FinancialEntryResponse, status_code=201)
def create_entry(
    payload: FinancialEntryCreate,
    svc: FinanceService = Depends(_svc),
) -> FinancialEntryResponse:
    return svc.create_entry(payload)


@finance_router.patch("/entries/{entry_id}", response_model=FinancialEntryResponse)
def update_entry(
    entry_id: int,
    payload: FinancialEntryUpdate,
    svc: FinanceService = Depends(_svc),
) -> FinancialEntryResponse:
    return svc.update_entry(entry_id, payload)


@finance_router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(
    entry_id: int,
    svc: FinanceService = Depends(_svc),
) -> None:
    svc.delete_entry(entry_id)


# ── Account Balances ──────────────────────────────────────────────


@finance_router.get("/account-balances", response_model=list[AccountBalanceSnapshotResponse])
def list_snapshots(
    month: str,
    svc: FinanceService = Depends(_svc),
) -> list[AccountBalanceSnapshotResponse]:
    return svc.list_snapshots(month)


@finance_router.post(
    "/account-balances", response_model=AccountBalanceSnapshotResponse, status_code=201
)
def create_snapshot(
    payload: AccountBalanceSnapshotCreate,
    svc: FinanceService = Depends(_svc),
) -> AccountBalanceSnapshotResponse:
    return svc.create_snapshot(payload)


@finance_router.patch(
    "/account-balances/{snapshot_id}", response_model=AccountBalanceSnapshotResponse
)
def update_snapshot(
    snapshot_id: int,
    payload: AccountBalanceSnapshotUpdate,
    svc: FinanceService = Depends(_svc),
) -> AccountBalanceSnapshotResponse:
    return svc.update_snapshot(snapshot_id, payload)


# ── Monthly Summary ───────────────────────────────────────────────


@finance_router.get("/monthly-summary", response_model=MonthlySummaryResponse)
def get_monthly_summary(
    month: str,
    svc: FinanceService = Depends(_svc),
) -> MonthlySummaryResponse:
    return svc.get_monthly_summary(month)
