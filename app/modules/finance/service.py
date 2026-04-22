"""Finance service — business logic for the Finance module."""

from __future__ import annotations

import re
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import (
    FinanceInvalidMonthRefError,
    FinanceMissingClosingError,
    FinanceNotFoundError,
)
from app.core.logging import get_logger
from app.db.repositories import (
    AccountBalanceSnapshotRepository,
    AccountRepository,
    FinancialEntryRepository,
    MonthlyClosingRepository,
)
from app.modules.finance.schemas import (
    AccountBalanceSnapshotCreate,
    AccountBalanceSnapshotResponse,
    AccountBalanceSnapshotUpdate,
    AccountCreate,
    AccountResponse,
    AccountSummary,
    AccountUpdate,
    FinancialEntryCreate,
    FinancialEntryResponse,
    FinancialEntryUpdate,
    MonthlyClosingCreate,
    MonthlyClosingResponse,
    MonthlyClosingUpdate,
    MonthlySummaryResponse,
)

logger = get_logger("modules.finance")

_MONTH_REF_RE = re.compile(r"^\d{4}-\d{2}$")


def _validate_month_ref(month_ref: str) -> None:
    if not _MONTH_REF_RE.match(month_ref):
        raise FinanceInvalidMonthRefError(month_ref)


class FinanceService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._accounts = AccountRepository(db)
        self._closings = MonthlyClosingRepository(db)
        self._entries = FinancialEntryRepository(db)
        self._snapshots = AccountBalanceSnapshotRepository(db)

    # ── Accounts ──────────────────────────────────────────────────

    def list_accounts(self) -> list[AccountResponse]:
        accounts = self._accounts.list_all()
        return [AccountResponse.model_validate(a) for a in accounts]

    def create_account(self, payload: AccountCreate) -> AccountResponse:
        account = self._accounts.create(
            name=payload.name,
            institution=payload.institution,
            is_active=payload.is_active,
        )
        logger.info("Conta criada: id=%d name=%s", account.id, account.name)
        return AccountResponse.model_validate(account)

    def update_account(self, account_id: int, payload: AccountUpdate) -> AccountResponse:
        account = self._accounts.get(account_id)
        if account is None:
            raise FinanceNotFoundError("Conta", account_id)
        changes = payload.model_dump(exclude_none=True)
        account = self._accounts.update(account, **changes)
        return AccountResponse.model_validate(account)

    # ── MonthlyClosing ────────────────────────────────────────────

    def get_monthly_closing(self, month_ref: str) -> MonthlyClosingResponse:
        _validate_month_ref(month_ref)
        closing = self._closings.get_by_month(month_ref)
        if closing is None:
            raise FinanceMissingClosingError(month_ref)
        return MonthlyClosingResponse.model_validate(closing)

    def create_monthly_closing(self, payload: MonthlyClosingCreate) -> MonthlyClosingResponse:
        closing = self._closings.create(
            month_ref=payload.month_ref,
            initial_balance=payload.initial_balance,
            notes=payload.notes,
        )
        logger.info("Fechamento criado: id=%d month=%s", closing.id, closing.month_ref)
        return MonthlyClosingResponse.model_validate(closing)

    def update_monthly_closing(
        self, closing_id: int, payload: MonthlyClosingUpdate
    ) -> MonthlyClosingResponse:
        closing = self._closings.get(closing_id)
        if closing is None:
            raise FinanceNotFoundError("Fechamento", closing_id)
        changes = payload.model_dump(exclude_none=True)
        closing = self._closings.update(closing, **changes)
        return MonthlyClosingResponse.model_validate(closing)

    # ── FinancialEntry ────────────────────────────────────────────

    def list_entries(self, month_ref: str) -> list[FinancialEntryResponse]:
        _validate_month_ref(month_ref)
        entries = self._entries.list_by_month(month_ref)
        return [FinancialEntryResponse.model_validate(e) for e in entries]

    def create_entry(self, payload: FinancialEntryCreate) -> FinancialEntryResponse:
        entry = self._entries.create(
            description=payload.description,
            amount=payload.amount,
            entry_type=payload.type,
            status=payload.status,
            month_ref=payload.month_ref,
            category=payload.category,
            due_date=payload.due_date,
            settlement_date=payload.settlement_date,
            is_investment=payload.is_investment,
            notes=payload.notes,
        )
        logger.info("Lançamento criado: id=%d month=%s type=%s", entry.id, entry.month_ref, entry.type)
        return FinancialEntryResponse.model_validate(entry)

    def update_entry(
        self, entry_id: int, payload: FinancialEntryUpdate
    ) -> FinancialEntryResponse:
        entry = self._entries.get(entry_id)
        if entry is None:
            raise FinanceNotFoundError("Lançamento", entry_id)
        changes = payload.model_dump(exclude_none=True)
        # type field is stored as "type" in DB but validated in schema as "type"
        entry = self._entries.update(entry, **changes)
        return FinancialEntryResponse.model_validate(entry)

    def delete_entry(self, entry_id: int) -> None:
        entry = self._entries.get(entry_id)
        if entry is None:
            raise FinanceNotFoundError("Lançamento", entry_id)
        self._entries.delete(entry)
        logger.info("Lançamento excluído: id=%d", entry_id)

    # ── AccountBalanceSnapshot ────────────────────────────────────

    def list_snapshots(self, month_ref: str) -> list[AccountBalanceSnapshotResponse]:
        _validate_month_ref(month_ref)
        snapshots = self._snapshots.list_by_month(month_ref)
        return [AccountBalanceSnapshotResponse.model_validate(s) for s in snapshots]

    def create_snapshot(
        self, payload: AccountBalanceSnapshotCreate
    ) -> AccountBalanceSnapshotResponse:
        account = self._accounts.get(payload.account_id)
        if account is None:
            raise FinanceNotFoundError("Conta", payload.account_id)
        snapshot = self._snapshots.create(
            account_id=payload.account_id,
            month_ref=payload.month_ref,
            balance=payload.balance,
            reference_date=payload.reference_date,
            notes=payload.notes,
        )
        logger.info(
            "Snapshot criado: id=%d account=%d month=%s",
            snapshot.id,
            snapshot.account_id,
            snapshot.month_ref,
        )
        return AccountBalanceSnapshotResponse.model_validate(snapshot)

    def update_snapshot(
        self, snapshot_id: int, payload: AccountBalanceSnapshotUpdate
    ) -> AccountBalanceSnapshotResponse:
        snapshot = self._snapshots.get(snapshot_id)
        if snapshot is None:
            raise FinanceNotFoundError("Snapshot", snapshot_id)
        changes = payload.model_dump(exclude_none=True)
        snapshot = self._snapshots.update(snapshot, **changes)
        return AccountBalanceSnapshotResponse.model_validate(snapshot)

    # ── Monthly Summary ───────────────────────────────────────────

    def get_monthly_summary(self, month_ref: str) -> MonthlySummaryResponse:
        _validate_month_ref(month_ref)

        closing = self._closings.get_by_month(month_ref)
        if closing is None:
            raise FinanceMissingClosingError(month_ref)

        entries = self._entries.list_by_month(month_ref)
        snapshots = self._snapshots.list_by_month(month_ref)

        zero = Decimal("0")

        expenses_paid = sum(
            (Decimal(str(e.amount)) for e in entries if e.type == "expense" and e.status == "settled"),
            zero,
        )
        expenses_pending = sum(
            (Decimal(str(e.amount)) for e in entries if e.type == "expense" and e.status == "pending"),
            zero,
        )
        income_received = sum(
            (Decimal(str(e.amount)) for e in entries if e.type == "income" and e.status == "settled"),
            zero,
        )
        income_pending = sum(
            (Decimal(str(e.amount)) for e in entries if e.type == "income" and e.status == "pending"),
            zero,
        )

        initial_balance = Decimal(str(closing.initial_balance))
        current_balance = initial_balance + income_received - expenses_paid
        projected_final_balance = current_balance + income_pending - expenses_pending

        account_summaries: list[AccountSummary] = []
        for snapshot in snapshots:
            account = self._accounts.get(snapshot.account_id)
            if account is not None:
                account_summaries.append(
                    AccountSummary(
                        account_id=account.id,
                        account_name=account.name,
                        institution=account.institution,
                        balance=Decimal(str(snapshot.balance)),
                    )
                )

        conference_total = sum((s.balance for s in account_summaries), zero)
        conference_difference = conference_total - current_balance

        logger.info(
            "Resumo calculado: month=%s balance=%s conference_diff=%s",
            month_ref,
            current_balance,
            conference_difference,
        )

        return MonthlySummaryResponse(
            month_ref=month_ref,
            initial_balance=initial_balance,
            expenses_paid=expenses_paid,
            expenses_pending=expenses_pending,
            income_received=income_received,
            income_pending=income_pending,
            current_balance=current_balance,
            projected_final_balance=projected_final_balance,
            conference_total=conference_total,
            conference_difference=conference_difference,
            accounts=account_summaries,
        )
