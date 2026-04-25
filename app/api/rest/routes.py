"""API route definitions for Atlas AI Assistant."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.schemas import (
    ApprovalResponse,
    CalendarResponse,
    ChatRequest,
    ChatResponse,
    DailyBriefingResponse,
    DriveFilesResponse,
    DriveSearchResponse,
    EmailDraftRequest,
    EventProposalRequest,
    FreeSlotsResponse,
    InboxSummaryResponse,
    NewsBriefingResponse,
)
from app.core.config import settings
from app.core.exceptions import AtlasError
from app.core.logging import get_logger
from app.db.session import get_db
from app.integrations.telegram_bot import TelegramBot, esc
from app.modules.approval.service import ApprovalService
from app.modules.briefing.news_service import NewsService
from app.modules.briefing.service import BriefingService
from app.modules.calendar.service import CalendarService
from app.modules.drive.service import DriveService
from app.modules.inbox.service import InboxService
from app.orchestrator.orchestrator import Orchestrator

router = APIRouter()
logger = get_logger("api.routes")


# ── Test ────────────────────────────────────────────────────────


@router.get("/admin/test-telegram")
def test_telegram():
    bot = TelegramBot()

    chat_id = settings.telegram_admin_chat_id

    if not chat_id:
        return {"error": "TELEGRAM_ADMIN_CHAT_ID não configurado"}

    bot.send_message(
        chat_id=chat_id,
        text="Teste Atlas funcionando"
    )

    return {"ok": True, "message": "Mensagem enviada"}


# ── Health ────────────────────────────────────────────────────────


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


# ── Chat UI ───────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
def chat_ui() -> HTMLResponse:
    html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Atlas AI Assistant</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f1117; color: #e2e8f0; height: 100vh; display: flex; flex-direction: column; }
  header { padding: 16px 24px; border-bottom: 1px solid #1e2433; display: flex; align-items: center; gap: 10px; }
  header h1 { font-size: 18px; font-weight: 600; color: #93c5fd; }
  header span { font-size: 12px; color: #64748b; }
  #messages { flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 16px; }
  .msg { max-width: 75%; display: flex; flex-direction: column; gap: 4px; }
  .msg.user { align-self: flex-end; align-items: flex-end; }
  .msg.bot { align-self: flex-start; align-items: flex-start; }
  .bubble { padding: 12px 16px; border-radius: 16px; font-size: 14px; line-height: 1.6; white-space: pre-wrap; word-break: break-word; }
  .msg.user .bubble { background: #2563eb; color: #fff; border-bottom-right-radius: 4px; }
  .msg.bot .bubble { background: #1e2433; color: #e2e8f0; border-bottom-left-radius: 4px; }
  .meta { font-size: 11px; color: #475569; padding: 0 4px; }
  .typing .bubble { background: #1e2433; color: #64748b; font-style: italic; }
  #input-area { padding: 16px 24px; border-top: 1px solid #1e2433; display: flex; gap: 10px; }
  #input { flex: 1; background: #1e2433; border: 1px solid #334155; border-radius: 12px; padding: 12px 16px; color: #e2e8f0; font-size: 14px; outline: none; resize: none; height: 48px; max-height: 120px; overflow-y: auto; }
  #input:focus { border-color: #2563eb; }
  #send { background: #2563eb; border: none; border-radius: 12px; color: #fff; padding: 12px 20px; cursor: pointer; font-size: 14px; font-weight: 500; white-space: nowrap; }
  #send:hover { background: #1d4ed8; }
  #send:disabled { background: #334155; cursor: not-allowed; }
  .hint { text-align: center; font-size: 12px; color: #334155; padding: 8px; }
</style>
</head>
<body>
<header>
  <h1>Atlas</h1>
  <span>AI Assistant</span>
</header>
<div id="messages">
  <div class="hint">Digite uma mensagem ou use /help para ver os comandos disponíveis.</div>
</div>
<div id="input-area">
  <textarea id="input" placeholder="Mensagem para o Atlas..." rows="1"></textarea>
  <button id="send">Enviar</button>
</div>
<script>
  const messagesEl = document.getElementById('messages');
  const inputEl = document.getElementById('input');
  const sendBtn = document.getElementById('send');

  function addMessage(text, role, meta) {
    const div = document.createElement('div');
    div.className = `msg ${role}`;
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    bubble.textContent = text;
    div.appendChild(bubble);
    if (meta) {
      const m = document.createElement('div');
      m.className = 'meta';
      m.textContent = meta;
      div.appendChild(m);
    }
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  async function sendMessage() {
    const text = inputEl.value.trim();
    if (!text) return;
    inputEl.value = '';
    inputEl.style.height = '48px';
    sendBtn.disabled = true;

    addMessage(text, 'user');
    const typing = addMessage('digitando...', 'bot typing');

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, user_id: 'web' }),
      });
      const data = await res.json();
      messagesEl.removeChild(typing);
      const meta = `intent: ${data.intent} · confiança: ${(data.confidence * 100).toFixed(0)}%`;
      addMessage(data.message, 'bot', meta);
    } catch (err) {
      messagesEl.removeChild(typing);
      addMessage('Erro ao conectar com o Atlas.', 'bot');
    } finally {
      sendBtn.disabled = false;
      inputEl.focus();
    }
  }

  sendBtn.addEventListener('click', sendMessage);
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
  inputEl.addEventListener('input', () => {
    inputEl.style.height = '48px';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
  });
  inputEl.focus();
</script>
</body>
</html>"""
    return HTMLResponse(content=html)


# ── Chat (main orchestrator entry point) ──────────────────────────


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    orchestrator = Orchestrator(db)
    result = orchestrator.handle_request(payload.user_id, payload.message)
    return ChatResponse(**result)


# ── Inbox ─────────────────────────────────────────────────────────


@router.get("/inbox/summary", response_model=InboxSummaryResponse)
def inbox_summary() -> InboxSummaryResponse:
    data = InboxService().summarize_emails()
    return InboxSummaryResponse(**data)


# ── Calendar ──────────────────────────────────────────────────────


@router.get("/calendar/today", response_model=CalendarResponse)
def calendar_today() -> CalendarResponse:
    data = CalendarService().get_today_events()
    return CalendarResponse(**data)


@router.get("/calendar/free-slots", response_model=FreeSlotsResponse)
def calendar_free_slots(duration: int = 60) -> FreeSlotsResponse:
    slots = CalendarService().find_free_slots(duration)
    return FreeSlotsResponse(slots=slots, total=len(slots))


@router.post("/calendar/propose-event", response_model=ApprovalResponse)
def propose_event(
    payload: EventProposalRequest,
    db: Session = Depends(get_db),
) -> ApprovalResponse:
    service = ApprovalService(db)
    action = service.create_event_proposal(payload.model_dump())
    return ApprovalResponse(id=action.id, status=action.status, type=action.type)


# ── Drive ─────────────────────────────────────────────────────────


@router.get("/drive/files", response_model=DriveFilesResponse)
def drive_files() -> DriveFilesResponse:
    data = DriveService().list_files()
    return DriveFilesResponse(**data)


@router.get("/drive/files/search", response_model=DriveSearchResponse)
def drive_search(q: str) -> DriveSearchResponse:
    data = DriveService().search_files(q)
    return DriveSearchResponse(**data)


# ── Email Drafts ──────────────────────────────────────────────────


@router.post("/drafts/email", response_model=ApprovalResponse)
def create_email_draft(
    payload: EmailDraftRequest,
    db: Session = Depends(get_db),
) -> ApprovalResponse:
    service = ApprovalService(db)
    action = service.create_email_draft(payload.model_dump())
    return ApprovalResponse(id=action.id, status=action.status, type=action.type)


# ── Approvals ─────────────────────────────────────────────────────


@router.post("/approvals/{draft_id}/approve", response_model=ApprovalResponse)
def approve_action(draft_id: int, db: Session = Depends(get_db)) -> ApprovalResponse:
    service = ApprovalService(db)
    draft = service.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail=f"Acao #{draft_id} nao encontrada.")
    try:
        updated = service.confirm(draft)
    except AtlasError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from None
    return ApprovalResponse(id=updated.id, status=updated.status, type=updated.type)


@router.post("/approvals/{draft_id}/reject", response_model=ApprovalResponse)
def reject_action(draft_id: int, db: Session = Depends(get_db)) -> ApprovalResponse:
    service = ApprovalService(db)
    draft = service.get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail=f"Acao #{draft_id} nao encontrada.")
    try:
        updated = service.reject(draft)
    except AtlasError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from None
    return ApprovalResponse(id=updated.id, status=updated.status, type=updated.type)


# Backward-compat alias
@router.post(
    "/approvals/{draft_id}/confirm",
    response_model=ApprovalResponse,
    include_in_schema=False,
)
def confirm_approval_compat(
    draft_id: int,
    db: Session = Depends(get_db),
) -> ApprovalResponse:
    return approve_action(draft_id, db)


# ── News ──────────────────────────────────────────────────────────


@router.get("/news", response_model=NewsBriefingResponse)
def news() -> NewsBriefingResponse:
    data = NewsService().summarize_news()
    return NewsBriefingResponse(**data)


@router.get("/news/briefing", response_model=NewsBriefingResponse)
def news_briefing() -> NewsBriefingResponse:
    return news()


# ── Daily Briefing ────────────────────────────────────────────────


@router.get("/briefing", response_model=DailyBriefingResponse)
def get_briefing(db: Session = Depends(get_db)) -> DailyBriefingResponse:
    data = BriefingService(db).run_daily_briefing()
    return DailyBriefingResponse(**data)


@router.post("/jobs/run-daily-briefing")
def run_daily_briefing(db: Session = Depends(get_db)) -> dict:
    return BriefingService(db).run_daily_briefing()


# ── Admin: proactive Telegram triggers ───────────────────────────


@router.post("/admin/trigger-briefing")
def trigger_briefing(db: Session = Depends(get_db)) -> dict:
    """Generate the daily briefing and push it to Telegram proactively.

    Requires TELEGRAM_ADMIN_CHAT_ID to be set in the environment.
    Fails explicitly (503) if the config is missing — never silently.
    """
    chat_id = settings.telegram_admin_chat_id
    if not chat_id:
        raise HTTPException(
            status_code=503,
            detail=(
                "TELEGRAM_ADMIN_CHAT_ID nao configurado. "
                "Defina esta variavel de ambiente antes de usar este endpoint."
            ),
        )

    briefing = BriefingService(db).run_daily_briefing()
    bot = TelegramBot()
    delivery = bot.send_briefing(chat_id, briefing)

    logger.info(
        "trigger-briefing: id=%s sent=%d failed=%d",
        briefing["id"], delivery["sent"], delivery["failed"],
    )

    # Complete delivery failure — don't mask as success
    if delivery["sent"] == 0 and delivery["total_blocks"] > 0:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Briefing gerado (id={briefing['id']}) mas todos os "
                f"{delivery['failed']} bloco(s) falharam no envio ao Telegram."
            ),
        )

    return {
        "ok": delivery["failed"] == 0,
        "briefing_id": briefing["id"],
        "blocks_sent": delivery["sent"],
        "blocks_failed": delivery["failed"],
        "total_blocks": delivery["total_blocks"],
    }


# ── Telegram Webhook ──────────────────────────────────────────────


# ── Feedback callbacks (Memory loop) ──────────────────────────────

# src letter → (memory source, memory event_type)
_FB_SRC_MAP: dict[str, tuple[str, str]] = {
    "e": ("email", "email_classified"),
    "n": ("news", "news_ranked"),
}

# sig token → feedback string persisted in memory_events.feedback
_FB_SIG_MAP: dict[str, str] = {
    "pos": "positive",
    "neg": "negative",
    "imp": "important",
}


def _parse_feedback_callback(data: str) -> tuple[str, str, str] | None:
    """Parse a `fb:<src>:<ref>:<sig>` callback. Return (src, ref, sig) or None.

    Strict validation: any deviation from the contract returns None so the
    webhook can short-circuit without persisting garbage.
    """
    if not isinstance(data, str) or not data.startswith("fb:"):
        return None
    parts = data.split(":", 3)
    if len(parts) != 4:
        return None
    _, src, ref, sig = parts
    if src not in _FB_SRC_MAP or sig not in _FB_SIG_MAP or not ref:
        return None
    return src, ref, sig


def _handle_feedback_callback(
    bot: TelegramBot,
    db: Session,
    callback_query_id: str,
    data: str,
) -> None:
    """Persist user feedback from a Telegram inline button. Fail-safe at every step.

    1. Invalid callback_data → log and answer "Feedback invalido."
    2. MemoryService raises → answer with the fallback message.
    3. answer_callback_query raises → log only; never propagate.
    """
    parsed = _parse_feedback_callback(data)
    if parsed is None:
        logger.warning("Feedback callback invalido: %s", data)
        try:
            if callback_query_id:
                bot.answer_callback_query(callback_query_id, "Feedback invalido.")
        except Exception as exc:
            logger.warning("Falha ao responder callback invalido: %s", exc)
        return

    src, ref, sig = parsed
    source, event_type = _FB_SRC_MAP[src]
    feedback = _FB_SIG_MAP[sig]

    saved = False
    try:
        from app.modules.memory.service import MemoryService

        saved = MemoryService(db).add_feedback(
            reference_id=ref,
            feedback=feedback,
            source=source,
            event_type=event_type,
        )
    except Exception as exc:
        logger.warning("Memory.add_feedback falhou no webhook: %s", exc)

    answer_text = (
        "Feedback registrado."
        if saved
        else "Não consegui salvar agora, mas registrei sua intenção."
    )
    try:
        if callback_query_id:
            bot.answer_callback_query(callback_query_id, answer_text)
    except Exception as exc:
        logger.warning("Falha ao responder callback de feedback: %s", exc)


def _translate_callback(data: str) -> str:
    """Convert callback_data to an orchestrator-compatible command.

    Patterns:
      cmd:/inbox   → /inbox
      fin:sum      → /finance
      apprv:42     → /approve 42
      rejct:42     → /reject 42
      approve:42   → /approve 42  (legacy compat)
      reject:42    → /reject 42   (legacy compat)
    """
    if data.startswith("cmd:"):
        return data[4:]
    if data == "fin:sum":
        return "/finance"
    if data.startswith("apprv:"):
        return f"/approve {data[6:]}"
    if data.startswith("rejct:"):
        return f"/reject {data[6:]}"
    # Legacy patterns kept for backward compatibility
    if ":" in data:
        prefix, _, tail = data.partition(":")
        if prefix in ("approve", "reject"):
            return f"/{prefix} {tail}"
    return data


def _handle_finance_callback(bot: TelegramBot, chat_id: str, data: str) -> None:
    """Handle Finance module menu callbacks (no orchestrator, no DB needed)."""
    if data == "fin:menu":
        bot.send_message(chat_id, "💰 Finanças", reply_markup=bot.build_finance_menu())
    elif data == "fin:help_exp":
        bot.send_message(
            chat_id,
            "➕ <b>Lançar despesa:</b>\n"
            "<code>/expense 250.00 Mercado</code>\n"
            "<code>/expense 1500 Aluguel</code>",
        )
    elif data == "fin:help_inc":
        bot.send_message(
            chat_id,
            "➕ <b>Lançar receita:</b>\n"
            "<code>/income 5000.00 Salário</code>\n"
            "<code>/income 1200 Freelance</code>",
        )
    elif data == "fin:help_bal":
        bot.send_message(
            chat_id,
            "🏦 <b>Atualizar saldo da conta:</b>\n"
            "<code>/balance Nubank 1500.00</code>\n"
            "<code>/balance XP Investimentos 3500.00</code>",
        )
    elif data in ("fin:back", "main:menu"):
        bot.send_message(chat_id, "🏠 Atlas", reply_markup=bot.build_main_menu())


def _send_pending_list(bot: TelegramBot, db: Session, chat_id: str) -> None:
    """List pending approvals with per-item approval buttons.

    Handled here (not in orchestrator) because /pending has no orchestrator intent mapping.
    """
    service = ApprovalService(db)
    pending = service.list_pending()

    if not pending:
        bot.send_message(chat_id, "Nenhuma acao pendente.")
        return

    bot.send_message(chat_id, f"<b>Pendencias ({len(pending)}):</b>")
    for draft in pending:
        text = f"<b>#{esc(draft.id)}</b> — <code>{esc(draft.type)}</code>"
        bot.send_message(chat_id, text, reply_markup=bot.build_approval_keyboard(draft.id))


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    update = await request.json()
    bot = TelegramBot()

    parsed = bot.parse_update(update)
    if not parsed:
        return {"ok": True}

    if not bot.is_authorized(parsed["user_id"]):
        logger.warning("Unauthorized Telegram user: %s", parsed["user_id"])
        return {"ok": True}

    raw_cb = parsed.get("text", "") if parsed["type"] == "callback" else ""

    # Feedback callbacks: handled (and answered) here. Short-circuit before the
    # generic spinner-removal so we can answer with a specific text.
    if parsed["type"] == "callback" and raw_cb.startswith("fb:"):
        _handle_feedback_callback(
            bot, db, parsed.get("callback_query_id", ""), raw_cb,
        )
        return {"ok": True}

    # Answer callback immediately — removes the loading spinner on the button
    if parsed["type"] == "callback" and parsed.get("callback_query_id"):
        bot.answer_callback_query(parsed["callback_query_id"])

    # Finance menu callbacks: intercepted here, never reach the orchestrator
    if parsed["type"] == "callback" and (
        (raw_cb.startswith("fin:") and raw_cb != "fin:sum") or raw_cb == "main:menu"
    ):
        _handle_finance_callback(bot, parsed["chat_id"], raw_cb)
        return {"ok": True}

    # Resolve final command (callback_data or raw text)
    command = (
        _translate_callback(parsed["text"])
        if parsed["type"] == "callback"
        else parsed["text"]
    )

    # /pending is intercepted here — no matching intent in the orchestrator
    if command.strip() == "/pending":
        _send_pending_list(bot, db, parsed["chat_id"])
        return {"ok": True}

    orchestrator = Orchestrator(db)
    result = orchestrator.handle_request(parsed["user_id"], command)

    # Escape orchestrator output before sending as HTML to prevent injection from external data
    bot.send_message(parsed["chat_id"], esc(result.get("message", "OK")))

    # Render individual items with feedback buttons (Memory loop, fail-safe).
    intent = result.get("intent")
    if intent == "get_inbox_summary":
        bot.send_inbox_items_with_feedback(parsed["chat_id"], result.get("data") or {})
    elif intent == "get_news":
        bot.send_news_items_with_feedback(parsed["chat_id"], result.get("data") or {})

    # After /start or /help, attach the interactive main menu
    if command.strip().split()[0] in ("/start", "/help", "/ajuda"):
        bot.send_message(
            parsed["chat_id"],
            "Navegacao rapida:",
            reply_markup=bot.build_main_menu(),
        )

    # If a draft was created, send its approval buttons
    draft_id = result.get("data", {}).get("draft_id")
    if draft_id:
        bot.send_message(
            parsed["chat_id"],
            f"Acao <b>#{esc(draft_id)}</b> aguardando aprovacao.",
            reply_markup=bot.build_approval_keyboard(draft_id),
        )

    return {"ok": True}
