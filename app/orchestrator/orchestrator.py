"""Orchestrator — central routing and intent handling for Atlas AI Assistant.

Receives natural-language messages, classifies intent, routes to the
correct service, and returns structured responses.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import (
    AtlasError,
    FinanceInvalidMonthRefError,
    FinanceMissingClosingError,
)
from app.core.logging import get_logger, log_action
from app.integrations.claude_client import ClaudeClient
from app.modules.approval.service import ApprovalService
from app.modules.briefing.news_service import NewsService
from app.modules.briefing.service import BriefingService
from app.modules.calendar.service import CalendarService
from app.modules.finance.schemas import FinancialEntryCreate
from app.modules.finance.service import FinanceService
from app.modules.finance.telegram import (
    FinanceTelegramError,
    current_month_ref,
    format_balance_ok,
    format_expense_ok,
    format_income_ok,
    format_summary,
    parse_balance_args,
    parse_entry_args,
    parse_month_ref,
    today_iso,
)
from app.modules.inbox.service import InboxService
from app.orchestrator.intent_classifier import ClassifiedIntent, Intent, IntentClassifier

logger = get_logger("agent.orchestrator")


class Orchestrator:
    """Main entry point for processing user requests."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.classifier = IntentClassifier()
        self.claude = ClaudeClient()
        self.inbox = InboxService()
        self.calendar = CalendarService()
        self.news = NewsService()
        self.briefing = BriefingService(db)
        self.approval = ApprovalService(db)
        self.finance = FinanceService(db)

    def _classify_with_fallback(self, message: str) -> ClassifiedIntent:
        """Classify intent using Claude first, then rule-based fallback.

        Slash commands always use rule-based (fast, reliable, no API cost).
        Natural language attempts Claude first; falls back on any failure or UNKNOWN.
        """
        if message.strip().startswith("/"):
            return self.classifier.classify(message)

        result = self.claude.classify_intent(message)
        if result:
            try:
                intent = Intent(result["intent"])
                if intent != Intent.UNKNOWN:
                    return ClassifiedIntent(
                        intent=intent,
                        confidence=float(result.get("confidence", 0.85)),
                        params=result.get("params", {}),
                    )
            except (ValueError, KeyError):
                pass

        return self.classifier.classify(message)

    def handle_request(self, user_id: str, message: str) -> dict:
        """Classify intent and route to the appropriate handler.

        Returns a dict with keys: intent, confidence, success, data, message.
        """
        classified = self._classify_with_fallback(message)

        log_action(
            logger,
            "handle_request",
            user_id=user_id,
            intent=classified.intent.value,
            confidence=classified.confidence,
        )

        handler = _HANDLERS.get(classified.intent, _handle_unknown)

        try:
            result = handler(self, user_id, classified)
        except AtlasError as exc:
            log_action(logger, "handler_error", user_id=user_id, error=exc.message)
            result = {"success": False, "data": {}, "message": exc.message}
        except Exception as exc:
            logger.exception("Erro inesperado no handler %s", classified.intent)
            result = {"success": False, "data": {}, "message": f"Erro interno: {exc}"}

        return {
            "intent": classified.intent.value,
            "confidence": classified.confidence,
            **result,
        }


# ── Individual handlers ───────────────────────────────────────────
# Each receives (self=Orchestrator, user_id, classified) → dict.


def _handle_inbox(orch: Orchestrator, user_id: str, _ci: ClassifiedIntent) -> dict:
    data = orch.inbox.summarize_emails()
    return {"success": True, "data": data, "message": data["summary"]}


def _handle_calendar(orch: Orchestrator, user_id: str, _ci: ClassifiedIntent) -> dict:
    agenda = orch.calendar.get_today_events()
    slots = orch.calendar.find_free_slots()

    lines = [agenda["summary"]]
    for evt in agenda.get("events", []):
        lines.append(f"  - {evt['start']} | {evt['title']}")
    if slots:
        lines.append(f"\nHorarios livres: {len(slots)} slot(s)")
        for s in slots:
            lines.append(f"  - {s['start']}-{s['end']} ({s['duration_minutes']}min)")

    return {
        "success": True,
        "data": {"agenda": agenda, "free_slots": slots},
        "message": "\n".join(lines),
    }


def _handle_create_event(orch: Orchestrator, user_id: str, _ci: ClassifiedIntent) -> dict:
    return {
        "success": True,
        "data": {"requires_details": True},
        "message": (
            "Para criar um evento, envie os detalhes:\n"
            "- Titulo\n"
            "- Data e hora de inicio\n"
            "- Data e hora de termino\n"
            "- Participantes (opcional)\n\n"
            "Ou use POST /calendar/propose-event com os dados estruturados."
        ),
    }


def _handle_news(orch: Orchestrator, user_id: str, _ci: ClassifiedIntent) -> dict:
    data = orch.news.summarize_news()
    lines = [data["summary"]]
    for item in data.get("items", [])[:5]:
        lines.append(f"  - {item['title']} [{item['category']}]")
    return {"success": True, "data": data, "message": "\n".join(lines)}


def _handle_briefing(orch: Orchestrator, user_id: str, _ci: ClassifiedIntent) -> dict:
    data = orch.briefing.run_daily_briefing()
    return {"success": True, "data": data, "message": data["content"]}


def _handle_approve(orch: Orchestrator, user_id: str, ci: ClassifiedIntent) -> dict:
    action_id = ci.params.get("action_id")
    if not action_id:
        pending = orch.approval.list_pending()
        if not pending:
            return {"success": True, "data": {}, "message": "Nenhuma acao pendente."}
        lines = ["Acoes pendentes:"]
        for d in pending:
            lines.append(f"  #{d.id} — {d.type} (criada em {d.created_at})")
        lines.append("\nUse: aprovar #ID")
        return {"success": False, "data": {"pending": len(pending)}, "message": "\n".join(lines)}

    draft = orch.approval.get_draft(int(action_id))
    if not draft:
        return {"success": False, "data": {}, "message": f"Acao #{action_id} nao encontrada."}

    updated = orch.approval.confirm(draft, user_id=user_id)
    return {
        "success": True,
        "data": {"id": updated.id, "status": updated.status, "type": updated.type},
        "message": f"Acao #{updated.id} ({updated.type}) aprovada.",
    }


def _handle_reject(orch: Orchestrator, user_id: str, ci: ClassifiedIntent) -> dict:
    action_id = ci.params.get("action_id")
    if not action_id:
        return {
            "success": False,
            "data": {},
            "message": "Informe o ID da acao. Exemplo: rejeitar #42",
        }

    draft = orch.approval.get_draft(int(action_id))
    if not draft:
        return {"success": False, "data": {}, "message": f"Acao #{action_id} nao encontrada."}

    updated = orch.approval.reject(draft, user_id=user_id)
    return {
        "success": True,
        "data": {"id": updated.id, "status": updated.status, "type": updated.type},
        "message": f"Acao #{updated.id} ({updated.type}) rejeitada.",
    }


def _handle_help(_orch: Orchestrator, _user_id: str, ci: ClassifiedIntent) -> dict:
    is_welcome = ci.params.get("welcome") == "true"
    commands = [
        "/inbox    — Resumo da caixa de entrada",
        "/agenda   — Agenda do dia + horarios livres",
        "/news     — Briefing de noticias",
        "/briefing — Briefing diario completo",
        "/approve {id} — Aprovar acao pendente",
        "/reject  {id} — Rejeitar acao pendente",
        "/finance [YYYY-MM] — Resumo financeiro do mes",
        "/expense <valor> <descricao> — Registrar despesa",
        "/income  <valor> <descricao> — Registrar receita",
        "/balance <conta> <valor>     — Registrar saldo de conta",
        "/help         — Mostrar esta ajuda",
    ]
    header = "Atlas AI Assistant iniciado.\n" if is_welcome else ""
    message = header + "Comandos disponiveis:\n" + "\n".join(commands)
    return {"success": True, "data": {"commands": commands}, "message": message}


# ── Finance handlers ──────────────────────────────────────────────


def _handle_finance_summary(orch: Orchestrator, _user_id: str, ci: ClassifiedIntent) -> dict:
    try:
        month_ref = parse_month_ref(ci.params.get("raw_args"))
    except FinanceTelegramError as exc:
        return {"success": False, "data": {}, "message": str(exc)}

    try:
        summary = orch.finance.get_monthly_summary(month_ref)
    except FinanceMissingClosingError:
        return {
            "success": False,
            "data": {"month_ref": month_ref},
            "message": "❌ Não existe fechamento para o mês informado",
        }
    except FinanceInvalidMonthRefError:
        return {"success": False, "data": {}, "message": "❌ Mês inválido. Use YYYY-MM"}

    return {
        "success": True,
        "data": summary.model_dump(mode="json"),
        "message": format_summary(summary),
    }


def _create_finance_entry(
    orch: Orchestrator,
    ci: ClassifiedIntent,
    *,
    entry_type: str,
    ok_formatter,
) -> dict:
    try:
        amount, description = parse_entry_args(ci.params.get("raw_args", ""))
    except FinanceTelegramError as exc:
        return {"success": False, "data": {}, "message": str(exc)}

    today = today_iso()
    payload = FinancialEntryCreate(
        description=description,
        amount=amount,
        type=entry_type,
        status="settled",
        month_ref=current_month_ref(),
        due_date=today,
        settlement_date=today,
    )
    entry = orch.finance.create_entry(payload)
    return {
        "success": True,
        "data": entry.model_dump(mode="json"),
        "message": ok_formatter(entry),
    }


def _handle_finance_expense(orch: Orchestrator, _user_id: str, ci: ClassifiedIntent) -> dict:
    return _create_finance_entry(
        orch, ci, entry_type="expense", ok_formatter=format_expense_ok
    )


def _handle_finance_income(orch: Orchestrator, _user_id: str, ci: ClassifiedIntent) -> dict:
    return _create_finance_entry(
        orch, ci, entry_type="income", ok_formatter=format_income_ok
    )


def _handle_finance_balance(orch: Orchestrator, _user_id: str, ci: ClassifiedIntent) -> dict:
    try:
        account_name, balance = parse_balance_args(ci.params.get("raw_args", ""))
    except FinanceTelegramError as exc:
        return {"success": False, "data": {}, "message": str(exc)}

    account = orch.finance.get_account_by_name(account_name)
    if account is None:
        return {
            "success": False,
            "data": {},
            "message": f"❌ Conta não encontrada: {account_name}",
        }

    snapshot = orch.finance.upsert_snapshot(
        account_id=account.id,
        month_ref=current_month_ref(),
        balance=balance,
        reference_date=today_iso(),
    )
    return {
        "success": True,
        "data": snapshot.model_dump(mode="json"),
        "message": format_balance_ok(account.name, snapshot),
    }


def _handle_unknown(_orch: Orchestrator, _user_id: str, _ci: ClassifiedIntent) -> dict:
    return {
        "success": True,
        "data": {},
        "message": (
            "Nao entendi o pedido. Posso ajudar com:\n"
            "- Inbox: resumo e emails prioritarios\n"
            "- Agenda: compromissos e horarios livres\n"
            "- Noticias: briefing por categoria\n"
            "- Briefing diario: consolidado completo\n\n"
            "Use /help para ver todos os comandos."
        ),
    }


# ── Handler dispatch table ────────────────────────────────────────

_HANDLERS: dict = {
    Intent.GET_INBOX_SUMMARY: _handle_inbox,
    Intent.GET_CALENDAR: _handle_calendar,
    Intent.CREATE_EVENT: _handle_create_event,
    Intent.GET_NEWS: _handle_news,
    Intent.GET_DAILY_BRIEFING: _handle_briefing,
    Intent.APPROVE_ACTION: _handle_approve,
    Intent.REJECT_ACTION: _handle_reject,
    Intent.GET_FINANCE_SUMMARY: _handle_finance_summary,
    Intent.CREATE_FINANCE_EXPENSE: _handle_finance_expense,
    Intent.CREATE_FINANCE_INCOME: _handle_finance_income,
    Intent.SET_FINANCE_BALANCE: _handle_finance_balance,
    Intent.HELP: _handle_help,
}
