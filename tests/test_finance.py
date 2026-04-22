"""Tests for the Finance module."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.exceptions import (
    FinanceDuplicateClosingError,
    FinanceDuplicateSnapshotError,
    FinanceInvalidMonthRefError,
    FinanceMissingClosingError,
    FinanceNotFoundError,
)
from app.modules.finance.service import FinanceService
from app.modules.finance.schemas import (
    AccountBalanceSnapshotCreate,
    AccountBalanceSnapshotUpdate,
    AccountCreate,
    AccountUpdate,
    FinancialEntryCreate,
    FinancialEntryUpdate,
    MonthlyClosingCreate,
    MonthlyClosingUpdate,
)

MONTH = "2026-04"


# ── Accounts ──────────────────────────────────────────────────────


def test_create_account(db_session):
    svc = FinanceService(db_session)
    account = svc.create_account(AccountCreate(name="Nubank", institution="Nu Pagamentos"))
    assert account.id is not None
    assert account.name == "Nubank"
    assert account.institution == "Nu Pagamentos"
    assert account.is_active is True


def test_list_accounts_empty(db_session):
    assert FinanceService(db_session).list_accounts() == []


def test_list_accounts_returns_all(db_session):
    svc = FinanceService(db_session)
    svc.create_account(AccountCreate(name="XP", institution="XP Investimentos"))
    svc.create_account(AccountCreate(name="Itaú"))
    svc.create_account(AccountCreate(name="Nubank"))
    assert len(svc.list_accounts()) == 3


def test_update_account(db_session):
    svc = FinanceService(db_session)
    account = svc.create_account(AccountCreate(name="XP"))
    updated = svc.update_account(account.id, AccountUpdate(institution="XP Investimentos"))
    assert updated.institution == "XP Investimentos"


def test_update_account_not_found(db_session):
    with pytest.raises(FinanceNotFoundError):
        FinanceService(db_session).update_account(9999, AccountUpdate(name="X"))


def test_update_account_deactivate(db_session):
    svc = FinanceService(db_session)
    account = svc.create_account(AccountCreate(name="Old"))
    updated = svc.update_account(account.id, AccountUpdate(is_active=False))
    assert updated.is_active is False


# ── Monthly Closing ───────────────────────────────────────────────


def test_create_monthly_closing(db_session):
    svc = FinanceService(db_session)
    closing = svc.create_monthly_closing(
        MonthlyClosingCreate(month_ref=MONTH, initial_balance=Decimal("1000.00"))
    )
    assert closing.id is not None
    assert closing.month_ref == MONTH
    assert closing.initial_balance == Decimal("1000.00")


def test_get_monthly_closing(db_session):
    svc = FinanceService(db_session)
    svc.create_monthly_closing(MonthlyClosingCreate(month_ref=MONTH, initial_balance=Decimal("500")))
    closing = svc.get_monthly_closing(MONTH)
    assert closing.month_ref == MONTH
    assert closing.initial_balance == Decimal("500")


def test_get_monthly_closing_not_found(db_session):
    with pytest.raises(FinanceMissingClosingError):
        FinanceService(db_session).get_monthly_closing("2025-01")


def test_monthly_closing_uniqueness(db_session):
    svc = FinanceService(db_session)
    svc.create_monthly_closing(MonthlyClosingCreate(month_ref=MONTH, initial_balance=Decimal("0")))
    with pytest.raises(FinanceDuplicateClosingError):
        svc.create_monthly_closing(MonthlyClosingCreate(month_ref=MONTH, initial_balance=Decimal("100")))


def test_update_monthly_closing(db_session):
    svc = FinanceService(db_session)
    closing = svc.create_monthly_closing(
        MonthlyClosingCreate(month_ref=MONTH, initial_balance=Decimal("100"))
    )
    updated = svc.update_monthly_closing(closing.id, MonthlyClosingUpdate(initial_balance=Decimal("200")))
    assert updated.initial_balance == Decimal("200")


def test_update_monthly_closing_not_found(db_session):
    with pytest.raises(FinanceNotFoundError):
        FinanceService(db_session).update_monthly_closing(9999, MonthlyClosingUpdate(notes="x"))


def test_invalid_month_ref_closing(db_session):
    with pytest.raises(Exception):
        # Pydantic raises ValidationError before service
        MonthlyClosingCreate(month_ref="04-2026", initial_balance=Decimal("0"))


def test_invalid_month_ref_service(db_session):
    svc = FinanceService(db_session)
    with pytest.raises(FinanceInvalidMonthRefError):
        svc.get_monthly_closing("abril-2026")


# ── Financial Entries ─────────────────────────────────────────────


def _entry(svc: FinanceService, **overrides) -> object:
    defaults = dict(
        description="Salário",
        amount=Decimal("5000.00"),
        type="income",
        status="settled",
        month_ref=MONTH,
    )
    defaults.update(overrides)
    return svc.create_entry(FinancialEntryCreate(**defaults))


def test_create_entry_income(db_session):
    svc = FinanceService(db_session)
    entry = _entry(svc)
    assert entry.id is not None
    assert entry.type == "income"
    assert entry.status == "settled"
    assert entry.amount == Decimal("5000.00")


def test_create_entry_expense(db_session):
    svc = FinanceService(db_session)
    entry = _entry(svc, description="Aluguel", amount=Decimal("1500"), type="expense", status="settled")
    assert entry.type == "expense"


def test_create_entry_pending(db_session):
    svc = FinanceService(db_session)
    entry = _entry(svc, status="pending")
    assert entry.status == "pending"


def test_entry_invalid_type(db_session):
    with pytest.raises(Exception):
        FinancialEntryCreate(
            description="X", amount=Decimal("10"), type="transfer", status="settled", month_ref=MONTH
        )


def test_entry_invalid_status(db_session):
    with pytest.raises(Exception):
        FinancialEntryCreate(
            description="X", amount=Decimal("10"), type="income", status="done", month_ref=MONTH
        )


def test_entry_invalid_month_ref(db_session):
    with pytest.raises(Exception):
        FinancialEntryCreate(
            description="X", amount=Decimal("10"), type="income", status="settled", month_ref="2026/04"
        )


def test_list_entries_by_month(db_session):
    svc = FinanceService(db_session)
    _entry(svc)
    _entry(svc, description="Freelance", amount=Decimal("800"), month_ref="2026-03")
    entries = svc.list_entries(MONTH)
    assert len(entries) == 1
    assert entries[0].month_ref == MONTH


def test_update_entry(db_session):
    svc = FinanceService(db_session)
    entry = _entry(svc, status="pending")
    updated = svc.update_entry(entry.id, FinancialEntryUpdate(status="settled"))
    assert updated.status == "settled"


def test_delete_entry(db_session):
    svc = FinanceService(db_session)
    entry = _entry(svc)
    svc.delete_entry(entry.id)
    assert svc.list_entries(MONTH) == []


def test_delete_entry_not_found(db_session):
    with pytest.raises(FinanceNotFoundError):
        FinanceService(db_session).delete_entry(9999)


def test_update_entry_not_found(db_session):
    with pytest.raises(FinanceNotFoundError):
        FinanceService(db_session).update_entry(9999, FinancialEntryUpdate(status="settled"))


# ── Account Balance Snapshots ─────────────────────────────────────


def _create_account(svc: FinanceService, name: str = "Nubank") -> object:
    return svc.create_account(AccountCreate(name=name))


def test_create_snapshot(db_session):
    svc = FinanceService(db_session)
    account = _create_account(svc)
    snapshot = svc.create_snapshot(
        AccountBalanceSnapshotCreate(account_id=account.id, month_ref=MONTH, balance=Decimal("2500.00"))
    )
    assert snapshot.id is not None
    assert snapshot.balance == Decimal("2500.00")
    assert snapshot.month_ref == MONTH


def test_snapshot_uniqueness(db_session):
    svc = FinanceService(db_session)
    account = _create_account(svc)
    svc.create_snapshot(
        AccountBalanceSnapshotCreate(account_id=account.id, month_ref=MONTH, balance=Decimal("100"))
    )
    with pytest.raises(FinanceDuplicateSnapshotError):
        svc.create_snapshot(
            AccountBalanceSnapshotCreate(account_id=account.id, month_ref=MONTH, balance=Decimal("200"))
        )


def test_snapshot_account_not_found(db_session):
    svc = FinanceService(db_session)
    with pytest.raises(FinanceNotFoundError):
        svc.create_snapshot(
            AccountBalanceSnapshotCreate(account_id=9999, month_ref=MONTH, balance=Decimal("100"))
        )


def test_list_snapshots_by_month(db_session):
    svc = FinanceService(db_session)
    a1 = _create_account(svc, "Nubank")
    a2 = _create_account(svc, "Itaú")
    svc.create_snapshot(AccountBalanceSnapshotCreate(account_id=a1.id, month_ref=MONTH, balance=Decimal("500")))
    svc.create_snapshot(AccountBalanceSnapshotCreate(account_id=a2.id, month_ref=MONTH, balance=Decimal("1000")))
    svc.create_snapshot(AccountBalanceSnapshotCreate(account_id=a1.id, month_ref="2026-03", balance=Decimal("400")))
    snapshots = svc.list_snapshots(MONTH)
    assert len(snapshots) == 2


def test_update_snapshot(db_session):
    svc = FinanceService(db_session)
    account = _create_account(svc)
    snapshot = svc.create_snapshot(
        AccountBalanceSnapshotCreate(account_id=account.id, month_ref=MONTH, balance=Decimal("100"))
    )
    updated = svc.update_snapshot(snapshot.id, AccountBalanceSnapshotUpdate(balance=Decimal("150")))
    assert updated.balance == Decimal("150")


def test_update_snapshot_not_found(db_session):
    with pytest.raises(FinanceNotFoundError):
        FinanceService(db_session).update_snapshot(9999, AccountBalanceSnapshotUpdate(balance=Decimal("1")))


# ── Monthly Summary ───────────────────────────────────────────────


def _setup_summary_scenario(db_session) -> FinanceService:
    """Creates closing, entries and snapshots for a full summary test."""
    svc = FinanceService(db_session)
    svc.create_monthly_closing(
        MonthlyClosingCreate(month_ref=MONTH, initial_balance=Decimal("1000.00"))
    )
    # income settled: 3000
    _entry(svc, description="Salário", amount=Decimal("3000.00"), type="income", status="settled")
    # income pending: 500
    _entry(svc, description="Freelance", amount=Decimal("500.00"), type="income", status="pending")
    # expense settled: 800
    _entry(svc, description="Aluguel", amount=Decimal("800.00"), type="expense", status="settled")
    # expense pending: 200
    _entry(svc, description="Cartão", amount=Decimal("200.00"), type="expense", status="pending")
    return svc


def test_monthly_summary_totals(db_session):
    svc = _setup_summary_scenario(db_session)
    summary = svc.get_monthly_summary(MONTH)

    assert summary.income_received == Decimal("3000.00")
    assert summary.income_pending == Decimal("500.00")
    assert summary.expenses_paid == Decimal("800.00")
    assert summary.expenses_pending == Decimal("200.00")


def test_monthly_summary_current_balance(db_session):
    svc = _setup_summary_scenario(db_session)
    summary = svc.get_monthly_summary(MONTH)
    # 1000 + 3000 - 800 = 3200
    assert summary.current_balance == Decimal("3200.00")


def test_monthly_summary_projected_balance(db_session):
    svc = _setup_summary_scenario(db_session)
    summary = svc.get_monthly_summary(MONTH)
    # 3200 + 500 - 200 = 3500
    assert summary.projected_final_balance == Decimal("3500.00")


def test_monthly_summary_conference(db_session):
    svc = _setup_summary_scenario(db_session)
    a1 = svc.create_account(AccountCreate(name="Nubank"))
    a2 = svc.create_account(AccountCreate(name="XP"))
    svc.create_snapshot(
        AccountBalanceSnapshotCreate(account_id=a1.id, month_ref=MONTH, balance=Decimal("1200.00"))
    )
    svc.create_snapshot(
        AccountBalanceSnapshotCreate(account_id=a2.id, month_ref=MONTH, balance=Decimal("2000.00"))
    )
    summary = svc.get_monthly_summary(MONTH)
    # conference_total = 1200 + 2000 = 3200
    assert summary.conference_total == Decimal("3200.00")
    # conference_difference = 3200 - 3200 = 0
    assert summary.conference_difference == Decimal("0")
    assert len(summary.accounts) == 2


def test_monthly_summary_conference_difference(db_session):
    svc = _setup_summary_scenario(db_session)
    account = svc.create_account(AccountCreate(name="Nubank"))
    svc.create_snapshot(
        AccountBalanceSnapshotCreate(account_id=account.id, month_ref=MONTH, balance=Decimal("3300.00"))
    )
    summary = svc.get_monthly_summary(MONTH)
    # conference_total = 3300, current_balance = 3200 → diff = 100
    assert summary.conference_difference == Decimal("100.00")


def test_monthly_summary_no_snapshots(db_session):
    svc = _setup_summary_scenario(db_session)
    summary = svc.get_monthly_summary(MONTH)
    assert summary.conference_total == Decimal("0")
    assert summary.conference_difference == -summary.current_balance
    assert summary.accounts == []


def test_monthly_summary_missing_closing(db_session):
    with pytest.raises(FinanceMissingClosingError):
        FinanceService(db_session).get_monthly_summary(MONTH)


def test_monthly_summary_invalid_month_ref(db_session):
    with pytest.raises(FinanceInvalidMonthRefError):
        FinanceService(db_session).get_monthly_summary("2026-4")


def test_monthly_summary_empty_entries(db_session):
    svc = FinanceService(db_session)
    svc.create_monthly_closing(
        MonthlyClosingCreate(month_ref=MONTH, initial_balance=Decimal("500.00"))
    )
    summary = svc.get_monthly_summary(MONTH)
    assert summary.current_balance == Decimal("500.00")
    assert summary.expenses_paid == Decimal("0")
    assert summary.income_received == Decimal("0")


# ── HTTP endpoints (no-regression + integration) ──────────────────


def test_health_still_works(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_http_create_account(client):
    response = client.post("/finance/accounts", json={"name": "Nubank", "institution": "Nu"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Nubank"
    assert data["id"] is not None


def test_http_list_accounts_empty(client):
    response = client.get("/finance/accounts")
    assert response.status_code == 200
    assert response.json() == []


def test_http_create_closing(client):
    response = client.post(
        "/finance/monthly-closing",
        json={"month_ref": MONTH, "initial_balance": "1000.00"},
    )
    assert response.status_code == 201
    assert response.json()["month_ref"] == MONTH


def test_http_duplicate_closing_returns_400(client):
    payload = {"month_ref": MONTH, "initial_balance": "0"}
    client.post("/finance/monthly-closing", json=payload)
    response = client.post("/finance/monthly-closing", json=payload)
    assert response.status_code == 400
    assert response.json()["error"] == "FINANCE_DUPLICATE_CLOSING"


def test_http_missing_closing_returns_400(client):
    response = client.get("/finance/monthly-summary", params={"month": MONTH})
    assert response.status_code == 400
    assert response.json()["error"] == "FINANCE_MISSING_CLOSING"


def test_http_invalid_month_ref_returns_400(client):
    response = client.get("/finance/monthly-summary", params={"month": "abril"})
    assert response.status_code == 400
    assert response.json()["error"] == "FINANCE_INVALID_MONTH_REF"


def test_http_create_and_delete_entry(client):
    client.post("/finance/monthly-closing", json={"month_ref": MONTH, "initial_balance": "0"})
    resp = client.post(
        "/finance/entries",
        json={
            "description": "Salário",
            "amount": "5000.00",
            "type": "income",
            "status": "settled",
            "month_ref": MONTH,
        },
    )
    assert resp.status_code == 201
    entry_id = resp.json()["id"]

    del_resp = client.delete(f"/finance/entries/{entry_id}")
    assert del_resp.status_code == 204

    entries = client.get("/finance/entries", params={"month": MONTH})
    assert entries.json() == []


def test_http_full_summary(client):
    client.post("/finance/monthly-closing", json={"month_ref": MONTH, "initial_balance": "1000"})
    client.post(
        "/finance/entries",
        json={"description": "Salário", "amount": "3000", "type": "income", "status": "settled", "month_ref": MONTH},
    )
    client.post(
        "/finance/entries",
        json={"description": "Aluguel", "amount": "1000", "type": "expense", "status": "settled", "month_ref": MONTH},
    )

    resp = client.get("/finance/monthly-summary", params={"month": MONTH})
    assert resp.status_code == 200
    data = resp.json()
    # current_balance = 1000 + 3000 - 1000 = 3000
    assert Decimal(data["current_balance"]) == Decimal("3000")
    assert Decimal(data["conference_total"]) == Decimal("0")
