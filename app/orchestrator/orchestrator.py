"""Orchestrator — central routing and intent handling for Atlas AI Assistant.

Receives natural-language messages, classifies intent, routes to the
correct service, and returns structured responses.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import AtlasError
from app.core.logging import get_logger, log_action
from app.integrations.claude_client import ClaudeClient
from app.modules.approval.service import ApprovalService
from app.modules.briefing.news_service import NewsService
from app.modules.briefing.service import BriefingService
from app.modules.calendar.service import CalendarService
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
        "/help         — Mostrar esta ajuda",
    ]
    header = "Atlas AI Assistant iniciado.\n" if is_welcome else ""
    message = header + "Comandos disponiveis:\n" + "\n".join(commands)
    return {"success": True, "data": {"commands": commands}, "message": message}


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
    Intent.HELP: _handle_help,
}
