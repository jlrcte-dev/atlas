"""Tests for the Telegram integration of the Finance module."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.modules.finance.schemas import (
    AccountCreate,
    MonthlyClosingCreate,
)
from app.modules.finance.service import FinanceService
from app.modules.finance.telegram import (
    FinanceTelegramError,
    current_month_ref,
    format_amount,
    format_summary,
    parse_amount,
    parse_balance_args,
    parse_entry_args,
    parse_month_ref,
)
from app.orchestrator.intent_classifier import Intent, IntentClassifier
from app.orchestrator.orchestrator import Orchestrator


# ── Parser: parse_amount ──────────────────────────────────────────


def test_parse_amount_dot_decimal():
    assert parse_amount("250.00") == Decimal("250.00")


def test_parse_amount_comma_decimal():
    assert parse_amount("250,00") == Decimal("250.00")


def test_parse_amount_integer():
    assert parse_amount("250") == Decimal("250")


def test_parse_amount_with_surrounding_spaces():
    assert parse_amount("  100.50  ") == Decimal("100.50")


def test_parse_amount_empty_raises():
    with pytest.raises(FinanceTelegramError) as excinfo:
        parse_amount("")
    assert "Valor inválido" in str(excinfo.value)


def test_parse_amount_non_numeric_raises():
    with pytest.raises(FinanceTelegramError):
        parse_amount("abc")


def test_parse_amount_zero_raises():
    with pytest.raises(FinanceTelegramError):
        parse_amount("0")


def test_parse_amount_negative_raises():
    with pytest.raises(FinanceTelegramError):
        parse_amount("-100")


def test_parse_amount_1500_accepted():
    assert parse_amount("1500") == Decimal("1500")


def test_parse_amount_1500_dot_accepted():
    assert parse_amount("1500.00") == Decimal("1500.00")


def test_parse_amount_1500_comma_accepted():
    assert parse_amount("1500,00") == Decimal("1500.00")


def test_parse_amount_ambiguous_dot_thousands_raises():
    with pytest.raises(FinanceTelegramError) as excinfo:
        parse_amount("1.500")
    assert "Valor ambíguo" in str(excinfo.value)


def test_parse_amount_ambiguous_comma_thousands_raises():
    with pytest.raises(FinanceTelegramError) as excinfo:
        parse_amount("1,500")
    assert "Valor ambíguo" in str(excinfo.value)


def test_parse_amount_both_separators_raises():
    with pytest.raises(FinanceTelegramError) as excinfo:
        parse_amount("1.500,00")
    assert "Valor ambíguo" in str(excinfo.value)


def test_parse_amount_brazilian_milhar_raises():
    with pytest.raises(FinanceTelegramError) as excinfo:
        parse_amount("1.234,56")
    assert "Valor ambíguo" in str(excinfo.value)


# ── Parser: parse_entry_args ──────────────────────────────────────


def test_parse_entry_args_simple():
    amount, desc = parse_entry_args("250.00 Atacadão")
    assert amount == Decimal("250.00")
    assert desc == "Atacadão"


def test_parse_entry_args_multi_word_description():
    amount, desc = parse_entry_args("1500 Feira do mês de abril")
    assert amount == Decimal("1500")
    assert desc == "Feira do mês de abril"


def test_parse_entry_args_missing_description_raises():
    with pytest.raises(FinanceTelegramError) as excinfo:
        parse_entry_args("250.00")
    assert "Descrição obrigatória" in str(excinfo.value)


def test_parse_entry_args_empty_raises():
    with pytest.raises(FinanceTelegramError):
        parse_entry_args("")


def test_parse_entry_args_invalid_amount_raises():
    with pytest.raises(FinanceTelegramError) as excinfo:
        parse_entry_args("abc Atacadão")
    assert "Valor inválido" in str(excinfo.value)


# ── Parser: parse_balance_args ────────────────────────────────────


def test_parse_balance_args_single_word_account():
    account, amount = parse_balance_args("XP 1850.00")
    assert account == "XP"
    assert amount == Decimal("1850.00")


def test_parse_balance_args_multi_word_account():
    account, amount = parse_balance_args("XP Investimentos 1850.00")
    assert account == "XP Investimentos"
    assert amount == Decimal("1850.00")


def test_parse_balance_args_missing_value_raises():
    with pytest.raises(FinanceTelegramError):
        parse_balance_args("XP")


def test_parse_balance_args_empty_raises():
    with pytest.raises(FinanceTelegramError):
        parse_balance_args("")


def test_parse_balance_args_invalid_amount_raises():
    with pytest.raises(FinanceTelegramError):
        parse_balance_args("XP abc")


# ── Parser: parse_month_ref ───────────────────────────────────────


def test_parse_month_ref_none_returns_current():
    assert parse_month_ref(None) == current_month_ref()


def test_parse_month_ref_empty_returns_current():
    assert parse_month_ref("") == current_month_ref()
    assert parse_month_ref("   ") == current_month_ref()


def test_parse_month_ref_valid():
    assert parse_month_ref("2026-04") == "2026-04"


def test_parse_month_ref_invalid_format_raises():
    with pytest.raises(FinanceTelegramError) as excinfo:
        parse_month_ref("abril")
    assert "Mês inválido" in str(excinfo.value)


def test_parse_month_ref_invalid_format_slash_raises():
    with pytest.raises(FinanceTelegramError):
        parse_month_ref("2026/04")


# ── Formatters ────────────────────────────────────────────────────


def test_format_amount_small():
    assert format_amount(Decimal("250.00")) == "R$ 250,00"


def test_format_amount_with_thousands():
    assert format_amount(Decimal("1234.56")) == "R$ 1.234,56"


def test_format_amount_zero():
    assert format_amount(Decimal("0")) == "R$ 0,00"


def test_format_amount_negative():
    assert format_amount(Decimal("-100.50")) == "R$ -100,50"


# ── IntentClassifier: finance commands ────────────────────────────


def test_classify_finance_no_args():
    c = IntentClassifier()
    result = c.classify("/finance")
    assert result.intent == Intent.GET_FINANCE_SUMMARY
    assert "raw_args" not in result.params


def test_classify_finance_with_month():
    c = IntentClassifier()
    result = c.classify("/finance 2026-04")
    assert result.intent == Intent.GET_FINANCE_SUMMARY
    assert result.params["raw_args"] == "2026-04"


def test_classify_expense_preserves_description_case():
    c = IntentClassifier()
    result = c.classify("/expense 250.00 Atacadão")
    assert result.intent == Intent.CREATE_FINANCE_EXPENSE
    assert result.params["raw_args"] == "250.00 Atacadão"


def test_classify_income_preserves_description_case():
    c = IntentClassifier()
    result = c.classify("/income 8000.00 Salário CLT")
    assert result.intent == Intent.CREATE_FINANCE_INCOME
    assert result.params["raw_args"] == "8000.00 Salário CLT"


def test_classify_balance_preserves_account_case():
    c = IntentClassifier()
    result = c.classify("/balance XP 1850.00")
    assert result.intent == Intent.SET_FINANCE_BALANCE
    assert result.params["raw_args"] == "XP 1850.00"


def test_classify_existing_commands_not_broken():
    """Regression: /approve 42 still extracts action_id."""
    c = IntentClassifier()
    result = c.classify("/approve 42")
    assert result.intent == Intent.APPROVE_ACTION
    assert result.params.get("action_id") == "42"


# ── Orchestrator: /finance ────────────────────────────────────────


def _seed_closing(db_session, month_ref: str, initial: str = "1000") -> None:
    FinanceService(db_session).create_monthly_closing(
        MonthlyClosingCreate(month_ref=month_ref, initial_balance=Decimal(initial))
    )


def test_finance_summary_current_month(db_session):
    _seed_closing(db_session, current_month_ref(), "500")
    result = Orchestrator(db_session).handle_request("u1", "/finance")
    assert result["intent"] == Intent.GET_FINANCE_SUMMARY.value
    assert result["success"] is True
    assert "📊 Financeiro" in result["message"]
    assert "Saldo inicial: R$ 500,00" in result["message"]


def test_finance_summary_specific_month(db_session):
    _seed_closing(db_session, "2026-04", "1000")
    result = Orchestrator(db_session).handle_request("u1", "/finance 2026-04")
    assert result["success"] is True
    assert "2026-04" in result["message"]


def test_finance_summary_invalid_month_format(db_session):
    result = Orchestrator(db_session).handle_request("u1", "/finance abril")
    assert result["success"] is False
    assert "Mês inválido" in result["message"]


def test_finance_summary_missing_closing(db_session):
    result = Orchestrator(db_session).handle_request("u1", "/finance 2099-12")
    assert result["success"] is False
    assert "Não existe fechamento" in result["message"]


# ── Orchestrator: /expense ────────────────────────────────────────


def test_expense_valid(db_session):
    result = Orchestrator(db_session).handle_request("u1", "/expense 250.00 Atacadão")
    assert result["intent"] == Intent.CREATE_FINANCE_EXPENSE.value
    assert result["success"] is True
    assert "Despesa registrada" in result["message"]
    assert "R$ 250,00" in result["message"]
    assert "Atacadão" in result["message"]
    # Entry persisted
    entries = FinanceService(db_session).list_entries(current_month_ref())
    assert len(entries) == 1
    assert entries[0].type == "expense"
    assert entries[0].status == "settled"
    assert entries[0].amount == Decimal("250.00")
    assert entries[0].description == "Atacadão"


def test_expense_missing_description(db_session):
    result = Orchestrator(db_session).handle_request("u1", "/expense 250.00")
    assert result["success"] is False
    assert "Descrição obrigatória" in result["message"]


def test_expense_invalid_amount(db_session):
    result = Orchestrator(db_session).handle_request("u1", "/expense abc café")
    assert result["success"] is False
    assert "Valor inválido" in result["message"]


def test_expense_no_args(db_session):
    result = Orchestrator(db_session).handle_request("u1", "/expense")
    assert result["success"] is False


# ── Orchestrator: /income ─────────────────────────────────────────


def test_income_valid(db_session):
    result = Orchestrator(db_session).handle_request("u1", "/income 8000.00 Salário")
    assert result["intent"] == Intent.CREATE_FINANCE_INCOME.value
    assert result["success"] is True
    assert "Receita registrada" in result["message"]
    assert "Salário" in result["message"]
    entries = FinanceService(db_session).list_entries(current_month_ref())
    assert len(entries) == 1
    assert entries[0].type == "income"
    assert entries[0].status == "settled"


# ── Orchestrator: /balance ────────────────────────────────────────


def _seed_account(db_session, name: str) -> int:
    return FinanceService(db_session).create_account(AccountCreate(name=name)).id


def test_balance_valid(db_session):
    _seed_account(db_session, "Nubank")
    result = Orchestrator(db_session).handle_request("u1", "/balance Nubank 2500.00")
    assert result["intent"] == Intent.SET_FINANCE_BALANCE.value
    assert result["success"] is True
    assert "Saldo registrado" in result["message"]
    assert "Nubank" in result["message"]
    assert "R$ 2.500,00" in result["message"]


def test_balance_case_insensitive_account_lookup(db_session):
    _seed_account(db_session, "Nubank")
    result = Orchestrator(db_session).handle_request("u1", "/balance nubank 500.00")
    assert result["success"] is True


def test_balance_multi_word_account(db_session):
    _seed_account(db_session, "XP Investimentos")
    result = Orchestrator(db_session).handle_request(
        "u1", "/balance XP Investimentos 3500.00"
    )
    assert result["success"] is True
    assert "XP Investimentos" in result["message"]


def test_balance_account_not_found(db_session):
    result = Orchestrator(db_session).handle_request("u1", "/balance XPTO 100.00")
    assert result["success"] is False
    assert "Conta não encontrada" in result["message"]
    assert "XPTO" in result["message"]


def test_balance_invalid_format(db_session):
    result = Orchestrator(db_session).handle_request("u1", "/balance XP")
    assert result["success"] is False


def test_balance_updates_existing_snapshot(db_session):
    """Second /balance call for same account+month updates instead of duplicating."""
    _seed_account(db_session, "Nubank")
    orch = Orchestrator(db_session)

    first = orch.handle_request("u1", "/balance Nubank 1000.00")
    assert first["success"] is True

    second = orch.handle_request("u1", "/balance Nubank 1500.00")
    assert second["success"] is True

    snapshots = FinanceService(db_session).list_snapshots(current_month_ref())
    assert len(snapshots) == 1
    assert snapshots[0].balance == Decimal("1500.00")


# ── Orchestrator ↔ FinanceService integration ─────────────────────


def test_summary_reflects_expense_via_telegram(db_session):
    """End-to-end: /expense creates an entry that shows up in /finance summary."""
    orch = Orchestrator(db_session)
    month = current_month_ref()
    _seed_closing(db_session, month, "1000")

    orch.handle_request("u1", "/expense 300 Café")
    result = orch.handle_request("u1", "/finance")

    assert result["success"] is True
    assert "Pago: R$ 300,00" in result["message"]
    # current_balance = 1000 - 300 = 700
    assert "Saldo atual: R$ 700,00" in result["message"]


def test_summary_reflects_income_via_telegram(db_session):
    orch = Orchestrator(db_session)
    month = current_month_ref()
    _seed_closing(db_session, month, "500")

    orch.handle_request("u1", "/income 2000 Salário")
    result = orch.handle_request("u1", "/finance")

    assert result["success"] is True
    assert "Recebido: R$ 2.000,00" in result["message"]
    # current_balance = 500 + 2000 = 2500
    assert "Saldo atual: R$ 2.500,00" in result["message"]


def test_summary_with_balance_shows_conference(db_session):
    orch = Orchestrator(db_session)
    month = current_month_ref()
    _seed_closing(db_session, month, "1000")
    _seed_account(db_session, "Nubank")

    orch.handle_request("u1", "/balance Nubank 950")
    result = orch.handle_request("u1", "/finance")

    assert result["success"] is True
    assert "Conferência: R$ 950,00" in result["message"]
    # current_balance = 1000, conference = 950 → diff = -50
    assert "Diferença: R$ -50,00" in result["message"]
    assert "- Nubank: R$ 950,00" in result["message"]


# ── format_summary standalone ─────────────────────────────────────


def test_format_summary_standalone(db_session):
    """Exercise format_summary directly on a realistic MonthlySummaryResponse."""
    svc = FinanceService(db_session)
    svc.create_monthly_closing(
        MonthlyClosingCreate(month_ref="2026-04", initial_balance=Decimal("1000"))
    )
    summary = svc.get_monthly_summary("2026-04")
    formatted = format_summary(summary)
    assert "📊 Financeiro — 2026-04" in formatted
    assert "Saldo inicial: R$ 1.000,00" in formatted
