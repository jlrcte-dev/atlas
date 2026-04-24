"""Telegram integration helpers for the Finance module.

Contains only parsing and formatting. All business logic lives in FinanceService.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.modules.finance.schemas import (
    AccountBalanceSnapshotResponse,
    FinancialEntryResponse,
    MonthlySummaryResponse,
)

_MONTH_REF_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_BR_FORMAT_RE = re.compile(r"^\d{1,3}(\.\d{3})*,\d{1,2}$")


class FinanceTelegramError(ValueError):
    """Parsing or validation error with a user-facing Portuguese message.

    The handler catches this and returns the message as-is to the user.
    """


# ── Date helpers ──────────────────────────────────────────────────


def current_month_ref() -> str:
    """Return current month as YYYY-MM (system local time)."""
    return datetime.now().strftime("%Y-%m")


def today_iso() -> str:
    """Return today as YYYY-MM-DD (system local time)."""
    return datetime.now().strftime("%Y-%m-%d")


# ── Parsers ───────────────────────────────────────────────────────


def parse_amount(raw: str) -> Decimal:
    """Parse a monetary value. Must be > 0.

    Accepted formats:
      250 / 1500              — integer
      250.00 / 1500.00        — US decimal (dot)
      250,00 / 1500,00        — BR decimal (comma)
      1.500,00 / 1.234,56     — BR full format (dot=milhar, comma=decimal)

    Rejected (ambiguous single separator + 3 digits):
      1.500 / 1,500
    """
    if raw is None or not raw.strip():
        raise FinanceTelegramError("❌ Valor inválido. Use formato 250.00")

    stripped = raw.strip()
    has_dot = "." in stripped
    has_comma = "," in stripped

    if has_dot and has_comma:
        # Accept Brazilian full format: X.XXX,XX — dot=milhar, comma=decimal
        if _BR_FORMAT_RE.match(stripped):
            normalized = stripped.replace(".", "").replace(",", ".")
        else:
            raise FinanceTelegramError("❌ Valor ambíguo. Use 1500, 1500.00 ou 1500,00.")
    elif has_dot or has_comma:
        # Reject single separator followed by exactly 3 digits (ambiguous thousands)
        sep = "." if has_dot else ","
        tail = stripped[stripped.rfind(sep) + 1:]
        if len(tail) == 3 and tail.isdigit():
            raise FinanceTelegramError("❌ Valor ambíguo. Use 1500, 1500.00 ou 1500,00.")
        normalized = stripped.replace(",", ".")
    else:
        normalized = stripped

    try:
        value = Decimal(normalized)
    except InvalidOperation:
        raise FinanceTelegramError("❌ Valor inválido. Use formato 250.00") from None
    if value <= 0:
        raise FinanceTelegramError("❌ Valor inválido. Use formato 250.00")
    return value


def parse_entry_args(raw_args: str) -> tuple[Decimal, str]:
    """Parse `/expense` or `/income` args: '<valor> <descrição>'.

    Returns (amount, description). Raises FinanceTelegramError on invalid input.
    """
    if not raw_args or not raw_args.strip():
        raise FinanceTelegramError("❌ Valor inválido. Use formato 250.00")

    parts = raw_args.strip().split(maxsplit=1)
    amount = parse_amount(parts[0])

    if len(parts) < 2 or not parts[1].strip():
        raise FinanceTelegramError("❌ Descrição obrigatória")

    description = parts[1].strip()
    return amount, description


def parse_balance_args(raw_args: str) -> tuple[str, Decimal]:
    """Parse `/balance` args: '<conta> <valor>'.

    The value is the LAST token; everything before is the account name (allows
    multi-word names like 'XP Investimentos 1850.00').
    """
    if not raw_args or not raw_args.strip():
        raise FinanceTelegramError(
            "❌ Formato inválido. Use: /balance <conta> <valor>"
        )

    parts = raw_args.strip().rsplit(maxsplit=1)
    if len(parts) < 2:
        raise FinanceTelegramError(
            "❌ Formato inválido. Use: /balance <conta> <valor>"
        )

    account_name = parts[0].strip()
    if not account_name:
        raise FinanceTelegramError(
            "❌ Formato inválido. Use: /balance <conta> <valor>"
        )

    amount = parse_amount(parts[1])
    return account_name, amount


def parse_month_ref(raw_args: str | None) -> str:
    """Parse an optional month_ref. Returns current month when absent/empty."""
    if raw_args is None or not raw_args.strip():
        return current_month_ref()
    candidate = raw_args.strip()
    if not _MONTH_REF_RE.match(candidate):
        raise FinanceTelegramError("❌ Mês inválido. Use YYYY-MM válido.")
    return candidate


# ── Formatters ────────────────────────────────────────────────────


def format_amount(value: Decimal) -> str:
    """Format a Decimal as 'R$ 1.234,56' (Brazilian locale, manual)."""
    q = Decimal(str(value)).quantize(Decimal("0.01"))
    # Python default: '1,234.56' (US). Swap to Brazilian: '1.234,56'.
    s = f"{q:,.2f}"
    s = s.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {s}"


def format_summary(summary: MonthlySummaryResponse) -> str:
    lines = [
        f"📊 Financeiro — {summary.month_ref}",
        "",
        f"Saldo inicial: {format_amount(summary.initial_balance)}",
        f"Recebido: {format_amount(summary.income_received)}",
        f"A receber: {format_amount(summary.income_pending)}",
        f"Pago: {format_amount(summary.expenses_paid)}",
        f"A pagar: {format_amount(summary.expenses_pending)}",
        "",
        f"Saldo atual: {format_amount(summary.current_balance)}",
        f"Saldo final: {format_amount(summary.projected_final_balance)}",
        "",
        f"Conferência: {format_amount(summary.conference_total)}",
        f"Diferença: {format_amount(summary.conference_difference)}",
    ]
    if summary.accounts:
        lines.append("")
        lines.append("Contas:")
        for account in summary.accounts:
            lines.append(f"- {account.account_name}: {format_amount(account.balance)}")
    return "\n".join(lines)


def format_expense_ok(entry: FinancialEntryResponse) -> str:
    return f"✅ Despesa registrada\n{format_amount(entry.amount)} — {entry.description}"


def format_income_ok(entry: FinancialEntryResponse) -> str:
    return f"✅ Receita registrada\n{format_amount(entry.amount)} — {entry.description}"


def format_balance_ok(
    account_name: str, snapshot: AccountBalanceSnapshotResponse
) -> str:
    return f"✅ Saldo registrado\n{account_name} — {format_amount(snapshot.balance)}"
