"""Tests for all service modules."""

from app.services.calendar_service import CalendarService
from app.services.inbox_service import InboxService
from app.services.news_service import NewsService

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


def test_calendar_today():
    result = CalendarService().get_today_events()
    assert result["total"] >= 1
    assert isinstance(result["events"], list)


def test_calendar_free_slots():
    slots = CalendarService().find_free_slots(duration_minutes=60)
    assert isinstance(slots, list)
    assert len(slots) >= 1
    for slot in slots:
        assert "start" in slot
        assert "end" in slot
        assert slot["duration_minutes"] >= 60


def test_calendar_free_slots_long_duration():
    slots = CalendarService().find_free_slots(duration_minutes=600)
    # Unlikely to have a 10-hour gap, may be empty — just verify structure
    assert isinstance(slots, list)


def test_calendar_propose_event():
    proposal = CalendarService().propose_event("Test Meeting", "10:00", "11:00")
    assert proposal["title"] == "Test Meeting"
    assert proposal["status"] == "proposal_ready"
    assert proposal["attendees"] == []


def test_calendar_backward_compat():
    result = CalendarService().get_today_agenda()
    assert "total" in result


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
