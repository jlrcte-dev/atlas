"""Pydantic request/response schemas for Atlas AI Assistant API."""

from __future__ import annotations

from pydantic import BaseModel, Field

# ── Chat ──────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    user_id: str = Field(default="default")


class ChatResponse(BaseModel):
    intent: str
    confidence: float
    success: bool
    data: dict = {}
    message: str


# ── Inbox ─────────────────────────────────────────────────────────


class InboxSummaryResponse(BaseModel):
    total: int
    high_priority: int
    medium_priority: int
    low_priority: int
    unread: int
    items: list[dict]
    action_items: list[dict]
    summary: str


# ── Calendar ──────────────────────────────────────────────────────


class CalendarResponse(BaseModel):
    total: int
    events: list[dict]
    summary: str


class FreeSlotsResponse(BaseModel):
    total: int
    slots: list[dict]


class EventProposalRequest(BaseModel):
    title: str
    start: str
    end: str
    attendees: list[str] = []
    location: str | None = None


# ── News ──────────────────────────────────────────────────────────


class NewsBriefingResponse(BaseModel):
    total: int
    categories: dict
    items: list[dict]
    summary: str


# ── Daily Briefing ────────────────────────────────────────────────


class DailyBriefingResponse(BaseModel):
    id: int
    content: str
    sections: dict = {}


# ── Approval ──────────────────────────────────────────────────────


class EmailDraftRequest(BaseModel):
    to: str
    subject: str
    body: str


class ApprovalResponse(BaseModel):
    id: int
    status: str
    type: str


# ── Drive ─────────────────────────────────────────────────────────


class DriveFilesResponse(BaseModel):
    total: int
    files: list[dict]
    summary: str


class DriveSearchResponse(BaseModel):
    total: int
    files: list[dict]
    query: str
    summary: str


# ── Errors ────────────────────────────────────────────────────────


class ErrorResponse(BaseModel):
    error: str
    message: str
