"""API route definitions for Atlas AI Assistant."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
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
from app.core.exceptions import AtlasError
from app.core.logging import get_logger
from app.db.session import get_db
from app.integrations.telegram_bot import TelegramBot
from app.modules.approval.service import ApprovalService
from app.modules.briefing.news_service import NewsService
from app.modules.briefing.service import BriefingService
from app.modules.calendar.service import CalendarService
from app.modules.drive.service import DriveService
from app.modules.inbox.service import InboxService
from app.orchestrator.orchestrator import Orchestrator

router = APIRouter()
logger = get_logger("api.routes")


# ── Health ────────────────────────────────────────────────────────


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


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


# ── Telegram Webhook ──────────────────────────────────────────────


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

    message_text = parsed["text"]

    # Translate callback-query data into a command the orchestrator understands
    if parsed["type"] == "callback" and ":" in message_text:
        action, action_id = message_text.split(":", 1)
        if action in ("approve", "reject"):
            message_text = f"/{action} {action_id}"
        if parsed.get("callback_query_id"):
            bot.answer_callback_query(parsed["callback_query_id"])

    orchestrator = Orchestrator(db)
    result = orchestrator.handle_request(parsed["user_id"], message_text)

    bot.send_message(parsed["chat_id"], result.get("message", "OK"))

    # If a draft was created, send approval buttons
    draft_id = result.get("data", {}).get("draft_id")
    if draft_id:
        bot.send_message(
            parsed["chat_id"],
            f"Acao #{draft_id} pendente de aprovacao.",
            reply_markup=bot.build_approval_keyboard(draft_id),
        )

    return {"ok": True}
