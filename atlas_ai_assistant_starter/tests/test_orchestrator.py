"""Tests for the orchestrator."""

from app.agent.orchestrator import Orchestrator


def test_handle_inbox(db_session):
    result = Orchestrator(db_session).handle_request("u1", "mostra meus emails")
    assert result["intent"] == "get_inbox_summary"
    assert result["success"] is True
    assert result["data"]["total"] >= 1


def test_handle_calendar(db_session):
    result = Orchestrator(db_session).handle_request("u1", "minha agenda hoje")
    assert result["intent"] == "get_calendar"
    assert result["success"] is True
    assert "agenda" in result["data"]
    assert "free_slots" in result["data"]


def test_handle_news(db_session):
    result = Orchestrator(db_session).handle_request("u1", "me mostra as noticias")
    assert result["intent"] == "get_news"
    assert result["success"] is True
    assert result["data"]["total"] >= 1


def test_handle_briefing(db_session):
    result = Orchestrator(db_session).handle_request("u1", "/briefing")
    assert result["intent"] == "get_daily_briefing"
    assert result["success"] is True
    assert "content" in result["data"]


def test_handle_create_event(db_session):
    result = Orchestrator(db_session).handle_request("u1", "criar evento amanha")
    assert result["intent"] == "create_event"
    assert result["success"] is True


def test_handle_approve_without_id(db_session):
    result = Orchestrator(db_session).handle_request("u1", "aprovar")
    assert result["intent"] == "approve_action"
    # No pending actions and no ID → lists pending (empty)
    assert "pendente" in result["message"].lower() or "nenhuma" in result["message"].lower()


def test_handle_approve_with_valid_draft(db_session):
    orch = Orchestrator(db_session)
    # Create a draft first
    draft = orch.approval.create_email_draft({"to": "x@y.com", "subject": "t", "body": "b"})
    result = orch.handle_request("u1", f"aprovar #{draft.id}")
    assert result["intent"] == "approve_action"
    assert result["success"] is True
    assert result["data"]["status"] == "approved"


def test_handle_reject_with_valid_draft(db_session):
    orch = Orchestrator(db_session)
    draft = orch.approval.create_event_proposal({"title": "M", "start": "10", "end": "11"})
    result = orch.handle_request("u1", f"/reject {draft.id}")
    assert result["intent"] == "reject_action"
    assert result["success"] is True
    assert result["data"]["status"] == "rejected"


def test_handle_approve_nonexistent(db_session):
    result = Orchestrator(db_session).handle_request("u1", "aprovar #9999")
    assert result["success"] is False
    assert "nao encontrada" in result["message"].lower()


def test_handle_help(db_session):
    result = Orchestrator(db_session).handle_request("u1", "/help")
    assert result["intent"] == "help"
    assert result["success"] is True
    assert "comandos" in result["message"].lower()


def test_handle_unknown(db_session):
    result = Orchestrator(db_session).handle_request("u1", "xyz nonsense")
    assert result["intent"] == "unknown"
