"""Tests for all service modules."""

from unittest.mock import patch

import pytest

from app.integrations.calendar_client import CalendarEvent
from app.integrations.drive_client import DriveFile
from app.services.calendar_service import CalendarService
from app.services.drive_service import DriveService
from app.services.inbox_service import InboxService
from app.services.news_service import NewsService

# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture()
def mock_calendar_events() -> list[CalendarEvent]:
    """Eventos mockados para isolar testes do CalendarService da API real."""
    return [
        CalendarEvent(
            id="evt_001",
            title="Call com equipe",
            start="09:00",
            end="10:00",
            all_day=False,
            location="Google Meet",
            attendees=["equipe@empresa.com"],
        ),
        CalendarEvent(
            id="evt_002",
            title="Almoco",
            start="12:00",
            end="13:00",
            all_day=False,
        ),
        CalendarEvent(
            id="evt_003",
            title="Revisao semanal",
            start="15:00",
            end="16:00",
            all_day=False,
            location="Escritorio",
            attendees=["gestor@empresa.com"],
        ),
    ]


@pytest.fixture()
def mock_calendar_events_with_allday() -> list[CalendarEvent]:
    """Eventos mockados incluindo evento de dia inteiro."""
    return [
        CalendarEvent(
            id="evt_allday",
            title="Feriado Nacional",
            start="2026-04-21",
            end="2026-04-22",
            all_day=True,
        ),
        CalendarEvent(
            id="evt_001",
            title="Call com equipe",
            start="09:00",
            end="10:00",
            all_day=False,
        ),
    ]

# ── Inbox ─────────────────────────────────────────────────────────


def test_inbox_summarize():
    result = InboxService().summarize_emails()
    assert result["total"] >= 1
    assert "high_priority" in result
    assert "medium_priority" in result
    assert "low_priority" in result
    assert "unread" in result
    assert isinstance(result["action_items"], list)


def test_inbox_get_recent():
    emails = InboxService().get_recent_emails()
    assert isinstance(emails, list)
    assert len(emails) >= 1
    assert "sender" in emails[0]
    assert "priority" in emails[0]


def test_inbox_backward_compat():
    result = InboxService().get_summary()
    assert "total" in result


# ── Calendar ──────────────────────────────────────────────────────


def test_calendar_today(mock_calendar_events):
    with patch(
        "app.integrations.calendar_client.GoogleCalendarClient.get_today_events",
        return_value=mock_calendar_events,
    ):
        result = CalendarService().get_today_events()
    assert result["total"] == 3
    assert isinstance(result["events"], list)
    assert result["events"][0]["title"] == "Call com equipe"


def test_calendar_free_slots(mock_calendar_events):
    with patch(
        "app.integrations.calendar_client.GoogleCalendarClient.get_today_events",
        return_value=mock_calendar_events,
    ):
        slots = CalendarService().find_free_slots(duration_minutes=60)
    assert isinstance(slots, list)
    assert len(slots) >= 1
    for slot in slots:
        assert "start" in slot
        assert "end" in slot
        assert slot["duration_minutes"] >= 60


def test_calendar_free_slots_long_duration(mock_calendar_events):
    with patch(
        "app.integrations.calendar_client.GoogleCalendarClient.get_today_events",
        return_value=mock_calendar_events,
    ):
        slots = CalendarService().find_free_slots(duration_minutes=600)
    # Improvável ter janela de 10h — só verifica estrutura
    assert isinstance(slots, list)


def test_calendar_propose_event():
    proposal = CalendarService().propose_event("Test Meeting", "10:00", "11:00")
    assert proposal["title"] == "Test Meeting"
    assert proposal["status"] == "proposal_ready"
    assert proposal["attendees"] == []


def test_calendar_allday_excluded_from_free_slots(mock_calendar_events_with_allday):
    """All-day events should not block free slot calculation."""
    with patch(
        "app.integrations.calendar_client.GoogleCalendarClient.get_today_events",
        return_value=mock_calendar_events_with_allday,
    ):
        slots = CalendarService().find_free_slots(duration_minutes=60)
    # All-day event is excluded, only the 09:00-10:00 blocks time
    # Should have slot 08:00-09:00 and 10:00-18:00
    assert isinstance(slots, list)
    assert len(slots) >= 1
    starts = [s["start"] for s in slots]
    assert "08:00" in starts


def test_calendar_allday_event_in_response(mock_calendar_events_with_allday):
    """All-day events should appear in the response with all_day=True."""
    with patch(
        "app.integrations.calendar_client.GoogleCalendarClient.get_today_events",
        return_value=mock_calendar_events_with_allday,
    ):
        result = CalendarService().get_today_events()
    allday_events = [e for e in result["events"] if e.get("all_day")]
    assert len(allday_events) == 1
    assert allday_events[0]["title"] == "Feriado Nacional"
    assert allday_events[0]["start"] == "2026-04-21"


def test_calendar_backward_compat(mock_calendar_events):
    with patch(
        "app.integrations.calendar_client.GoogleCalendarClient.get_today_events",
        return_value=mock_calendar_events,
    ):
        result = CalendarService().get_today_agenda()
    assert "total" in result


# ── Drive ─────────────────────────────────────────────────────────


@pytest.fixture()
def mock_drive_files() -> list[DriveFile]:
    return [
        DriveFile(
            id="file_001",
            name="Contrato Fornecedor A.pdf",
            mime_type="application/pdf",
            modified_time="2026-04-10T14:00:00Z",
            size=204800,
            web_view_link="https://drive.google.com/file/d/file_001/view",
            parents=["folder_root"],
        ),
        DriveFile(
            id="file_002",
            name="Proposta Comercial Q1.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            modified_time="2026-04-09T10:30:00Z",
            size=51200,
            web_view_link="https://drive.google.com/file/d/file_002/view",
            parents=["folder_root"],
        ),
        DriveFile(
            id="file_003",
            name="Planilha Budget 2026",
            mime_type="application/vnd.google-apps.spreadsheet",
            modified_time="2026-04-08T09:00:00Z",
            size=None,  # Google native format has no byte size
            web_view_link="https://drive.google.com/file/d/file_003/view",
            parents=["folder_root"],
        ),
    ]


def test_drive_list_files(mock_drive_files):
    with patch(
        "app.integrations.drive_client.GoogleDriveClient.list_files",
        return_value=mock_drive_files,
    ):
        result = DriveService().list_files()
    assert result["total"] == 3
    assert isinstance(result["files"], list)
    assert result["files"][0]["name"] == "Contrato Fornecedor A.pdf"
    assert "summary" in result


def test_drive_list_files_empty():
    with patch(
        "app.integrations.drive_client.GoogleDriveClient.list_files",
        return_value=[],
    ):
        result = DriveService().list_files()
    assert result["total"] == 0
    assert result["files"] == []


def test_drive_search_files(mock_drive_files):
    contrato_files = [f for f in mock_drive_files if "Contrato" in f.name]
    with patch(
        "app.integrations.drive_client.GoogleDriveClient.search_files",
        return_value=contrato_files,
    ):
        result = DriveService().search_files("Contrato")
    assert result["total"] == 1
    assert result["query"] == "Contrato"
    assert result["files"][0]["name"] == "Contrato Fornecedor A.pdf"


def test_drive_search_files_no_results():
    with patch(
        "app.integrations.drive_client.GoogleDriveClient.search_files",
        return_value=[],
    ):
        result = DriveService().search_files("xyz_inexistente")
    assert result["total"] == 0
    assert isinstance(result["files"], list)


def test_drive_file_size_none(mock_drive_files):
    """Google native formats have size=None — should be handled correctly."""
    with patch(
        "app.integrations.drive_client.GoogleDriveClient.list_files",
        return_value=mock_drive_files,
    ):
        result = DriveService().list_files()
    spreadsheet = next(f for f in result["files"] if "Budget" in f["name"])
    assert spreadsheet["size"] is None


# ── News ──────────────────────────────────────────────────────────


def test_news_summarize():
    result = NewsService().summarize_news()
    assert result["total"] >= 1
    assert "categories" in result
    assert isinstance(result["categories"], dict)
    assert isinstance(result["items"], list)


def test_news_fetch_rss():
    articles = NewsService().fetch_rss()
    assert isinstance(articles, list)
    assert len(articles) >= 1


def test_news_normalize():
    articles = NewsService().normalize_articles()
    assert isinstance(articles, list)
    for a in articles:
        assert "title" in a
        assert "category" in a
        assert "link" in a
        assert "summary" in a


def test_news_backward_compat():
    result = NewsService().get_briefing()
    assert "total" in result
