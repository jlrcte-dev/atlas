"""Tests for the Telegram feedback loop (Phase 2A · Step 2).

Coverage:
- callback parser (`fb:<src>:<ref>:<sig>`) — valid + invalid cases
- callback length stays within Telegram's 64-byte budget
- feedback persistence in memory_events.feedback (positive/negative/important)
- fail-safe: malformed callback / missing event / Memory failure
- regression: existing Telegram commands continue to work
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.api.rest.routes import (
    _FB_SIG_MAP,
    _FB_SRC_MAP,
    _handle_feedback_callback,
    _parse_feedback_callback,
)
from app.integrations.telegram_bot import TelegramBot
from app.modules.memory.service import MemoryService
from app.modules.memory.utils import to_callback_ref


# ── Parser ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ("fb:e:abc123:pos", ("e", "abc123", "pos")),
        ("fb:e:abc123:neg", ("e", "abc123", "neg")),
        ("fb:e:abc123:imp", ("e", "abc123", "imp")),
        ("fb:n:9f8e7d6c:pos", ("n", "9f8e7d6c", "pos")),
        ("fb:n:9f8e7d6c:neg", ("n", "9f8e7d6c", "neg")),
        ("fb:n:9f8e7d6c:imp", ("n", "9f8e7d6c", "imp")),
        # ref containing non-alphanumeric chars must still parse — split is on `:` only
        ("fb:e:msg-with_dashes:pos", ("e", "msg-with_dashes", "pos")),
    ],
)
def test_parser_valid(data, expected):
    assert _parse_feedback_callback(data) == expected


@pytest.mark.parametrize(
    "data",
    [
        "",
        "fin:sum",                    # different prefix
        "fb:e:abc",                   # missing sig
        "fb:e::pos",                  # empty ref
        "fb:x:abc:pos",               # invalid src
        "fb:e:abc:foo",               # invalid sig
        "fb:e:abc:POS",               # case-sensitive — only lowercase accepted
        "FB:e:abc:pos",               # case-sensitive prefix
        "not_a_feedback",             # no prefix
    ],
)
def test_parser_invalid_returns_none(data):
    assert _parse_feedback_callback(data) is None


def test_parser_handles_non_string_input():
    # Defensive: wrong type must not raise
    assert _parse_feedback_callback(None) is None  # type: ignore[arg-type]
    assert _parse_feedback_callback(123) is None   # type: ignore[arg-type]


# ── Callback length budget ────────────────────────────────────────────────────

def test_to_callback_ref_short_input_unchanged():
    assert to_callback_ref("18d3f4a5b6c7e8f9") == "18d3f4a5b6c7e8f9"


def test_to_callback_ref_empty_input():
    assert to_callback_ref("") == ""


def test_to_callback_ref_long_input_is_hashed_to_max_len():
    long_url = "https://economia.uol.com.br/bolsa-de-valores/noticias/2026/04/25/very-long-url.htm"
    ref = to_callback_ref(long_url)
    assert len(ref) == 32
    # deterministic
    assert ref == to_callback_ref(long_url)


def test_to_callback_ref_different_inputs_yield_different_refs():
    a = to_callback_ref("https://example.com/a" * 5)
    b = to_callback_ref("https://example.com/b" * 5)
    assert a != b


def test_feedback_keyboard_callback_data_under_64_bytes():
    """Telegram rejects callback_data > 64 bytes. Our budget must always fit."""
    long_id = "x" * 200
    short = to_callback_ref(long_id)
    kb = TelegramBot.build_feedback_keyboard("e", short)
    for row in kb["inline_keyboard"]:
        for btn in row:
            assert len(btn["callback_data"].encode("utf-8")) <= 64, btn["callback_data"]


def test_feedback_keyboard_has_three_buttons_per_item():
    kb = TelegramBot.build_feedback_keyboard("e", "abc")
    [row] = kb["inline_keyboard"]
    assert len(row) == 3
    sigs = [btn["callback_data"].rsplit(":", 1)[1] for btn in row]
    assert sigs == ["pos", "neg", "imp"]


# ── Persistence ───────────────────────────────────────────────────────────────

def _seed_event(svc: MemoryService, **overrides) -> str:
    payload = {
        "event_type": "email_classified",
        "source": "email",
        "reference_id": "ref_seed",
        "payload": {"category": "action"},
    }
    payload.update(overrides)
    svc.log_event(**payload)
    return payload["reference_id"]


def test_feedback_positive_persists_on_email(db_session):
    svc = MemoryService(db_session)
    ref = _seed_event(svc, reference_id="email_ref_pos")

    bot = MagicMock(spec=TelegramBot)
    _handle_feedback_callback(bot, db_session, "cbq_1", f"fb:e:{ref}:pos")

    events = svc.get_recent_events(event_type="email_classified")
    assert events[0].feedback == "positive"
    bot.answer_callback_query.assert_called_once_with("cbq_1", "Feedback registrado.")


def test_feedback_negative_persists_on_news(db_session):
    svc = MemoryService(db_session)
    ref = _seed_event(
        svc,
        event_type="news_ranked",
        source="news",
        reference_id="news_ref_neg",
        payload={"title": "Mercado hoje"},
    )

    bot = MagicMock(spec=TelegramBot)
    _handle_feedback_callback(bot, db_session, "cbq_2", f"fb:n:{ref}:neg")

    events = svc.get_recent_events(event_type="news_ranked")
    assert events[0].feedback == "negative"
    bot.answer_callback_query.assert_called_once_with("cbq_2", "Feedback registrado.")


def test_feedback_important_persists(db_session):
    svc = MemoryService(db_session)
    ref = _seed_event(svc, reference_id="email_ref_imp")

    bot = MagicMock(spec=TelegramBot)
    _handle_feedback_callback(bot, db_session, "cbq_3", f"fb:e:{ref}:imp")

    events = svc.get_recent_events()
    assert events[0].feedback == "important"


def test_feedback_with_event_type_disambiguates_collision(db_session):
    """When two events share a reference_id but differ in event_type,
    the feedback must hit the matching event_type only."""
    svc = MemoryService(db_session)
    shared = "shared_ref_xyz"
    svc.log_event("email_classified", "email", shared, {"category": "action"})
    svc.log_event("news_ranked", "news", shared, {"title": "x"})

    bot = MagicMock(spec=TelegramBot)
    _handle_feedback_callback(bot, db_session, "cbq", f"fb:n:{shared}:pos")

    email_events = svc.get_recent_events(event_type="email_classified")
    news_events = svc.get_recent_events(event_type="news_ranked")
    assert email_events[0].feedback is None
    assert news_events[0].feedback == "positive"


def test_feedback_for_missing_event_returns_fallback_message(db_session):
    """When no matching event exists, the user gets the 'soft fail' message."""
    bot = MagicMock(spec=TelegramBot)
    _handle_feedback_callback(bot, db_session, "cbq", "fb:e:nonexistent_ref:pos")

    bot.answer_callback_query.assert_called_once_with(
        "cbq", "Não consegui salvar agora, mas registrei sua intenção."
    )


# ── Fail-safe ─────────────────────────────────────────────────────────────────

def test_invalid_callback_does_not_persist(db_session):
    bot = MagicMock(spec=TelegramBot)
    _handle_feedback_callback(bot, db_session, "cbq", "fb:e:")

    bot.answer_callback_query.assert_called_once_with("cbq", "Feedback invalido.")


def test_memory_service_failure_does_not_break_webhook(db_session):
    """A raise inside MemoryService must be swallowed and the user still answered."""
    bot = MagicMock(spec=TelegramBot)

    with patch(
        "app.modules.memory.service.MemoryService.add_feedback",
        side_effect=RuntimeError("DB down"),
    ):
        # Must not raise
        _handle_feedback_callback(bot, db_session, "cbq", "fb:e:ref_x:pos")

    # User still gets a response
    bot.answer_callback_query.assert_called_once()
    args, _kwargs = bot.answer_callback_query.call_args
    assert args[1] == "Não consegui salvar agora, mas registrei sua intenção."


def test_answer_callback_failure_does_not_propagate(db_session):
    """Even if Telegram answer_callback_query fails, the handler must not raise."""
    svc = MemoryService(db_session)
    ref = _seed_event(svc, reference_id="ans_fail_ref")

    bot = MagicMock(spec=TelegramBot)
    bot.answer_callback_query.side_effect = RuntimeError("network down")

    # Must not raise
    _handle_feedback_callback(bot, db_session, "cbq", f"fb:e:{ref}:pos")

    # Feedback was still saved
    assert svc.get_recent_events()[0].feedback == "positive"


def test_empty_callback_query_id_is_handled(db_session):
    """If Telegram sends no callback_query_id, the handler must still complete."""
    svc = MemoryService(db_session)
    ref = _seed_event(svc, reference_id="no_cbq_ref")

    bot = MagicMock(spec=TelegramBot)
    _handle_feedback_callback(bot, db_session, "", f"fb:e:{ref}:pos")

    bot.answer_callback_query.assert_not_called()
    assert svc.get_recent_events()[0].feedback == "positive"


# ── Send helpers fail-safe ────────────────────────────────────────────────────

def test_send_inbox_items_with_feedback_skips_items_without_id():
    bot = TelegramBot()
    bot.send_message = MagicMock(return_value={"ok": True})

    inbox_data = {
        "top5": [
            {"id": "msg_001", "subject": "Reuniao", "sender": "x@y.com",
             "priority": "alta", "short_reason": "deadline"},
            {"id": "", "subject": "no id", "sender": "z@y.com", "priority": "baixa"},
        ]
    }
    bot.send_inbox_items_with_feedback("123", inbox_data)
    assert bot.send_message.call_count == 1


def test_send_news_items_with_feedback_uses_link_as_ref():
    bot = TelegramBot()
    bot.send_message = MagicMock(return_value={"ok": True})

    long_link = "https://example.com/" + "x" * 200
    news_data = {
        "items": [
            {"link": long_link, "title": "T1", "category": "macro", "priority": "high"},
        ]
    }
    bot.send_news_items_with_feedback("123", news_data)

    assert bot.send_message.call_count == 1
    _args, kwargs = bot.send_message.call_args
    cb = kwargs["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    assert cb.startswith("fb:n:")
    assert len(cb.encode("utf-8")) <= 64


def test_send_inbox_handles_empty_top5():
    bot = TelegramBot()
    bot.send_message = MagicMock(return_value={"ok": True})
    bot.send_inbox_items_with_feedback("123", {"top5": []})
    bot.send_message.assert_not_called()


def test_send_inbox_does_not_raise_on_internal_failure():
    """A malformed item must not abort the webhook."""
    bot = TelegramBot()
    bot.send_message = MagicMock(side_effect=RuntimeError("kaboom"))
    # Top-level try/except must absorb the failure
    bot.send_inbox_items_with_feedback("123", {"top5": [{"id": "x"}]})


# ── add_feedback backward compatibility ───────────────────────────────────────

def test_add_feedback_returns_true_when_event_found(db_session):
    svc = MemoryService(db_session)
    svc.log_event("email_classified", "email", "ref_ok", {})
    assert svc.add_feedback("ref_ok", "positive") is True


def test_add_feedback_returns_false_when_event_missing(db_session):
    svc = MemoryService(db_session)
    assert svc.add_feedback("does_not_exist", "positive") is False


def test_add_feedback_with_source_filter(db_session):
    svc = MemoryService(db_session)
    svc.log_event("email_classified", "email", "shared", {})
    svc.log_event("news_ranked", "news", "shared", {})

    saved = svc.add_feedback("shared", "positive", source="news")
    assert saved is True

    email_events = svc.get_recent_events(event_type="email_classified")
    news_events = svc.get_recent_events(event_type="news_ranked")
    assert email_events[0].feedback is None
    assert news_events[0].feedback == "positive"


# ── Constants integrity ───────────────────────────────────────────────────────

def test_src_map_has_email_and_news_only():
    assert set(_FB_SRC_MAP.keys()) == {"e", "n"}


def test_sig_map_has_three_signals():
    assert _FB_SIG_MAP == {
        "pos": "positive",
        "neg": "negative",
        "imp": "important",
    }


# ── Regression: Telegram intent classifier still maps existing commands ───────

@pytest.mark.parametrize(
    ("command", "expected_intent"),
    [
        ("/inbox", "get_inbox_summary"),
        ("/news", "get_news"),
        ("/briefing", "get_daily_briefing"),
        ("/finance", "get_finance_summary"),
        ("/expense 250 Mercado", "create_finance_expense"),
        ("/income 5000 Salario", "create_finance_income"),
        ("/balance Nubank 1500", "set_finance_balance"),
    ],
)
def test_intent_classifier_regression(command, expected_intent):
    from app.orchestrator.intent_classifier import IntentClassifier

    classified = IntentClassifier().classify(command)
    assert classified.intent.value == expected_intent


# ── E2E hash invariant (logging ↔ button) ────────────────────────────────────
#
# These tests prove the central invariant of the feedback loop:
#   the reference_id stored in `memory_events` is the SAME value that ends up
#   inside `callback_data`. If a future change breaks `to_callback_ref` symmetry
#   between writer and reader, these tests fail loudly.

from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker


@contextmanager
def _patched_session_local(test_db_session):
    """Patch `app.db.session.SessionLocal` so out-of-band logging paths
    (`_log_email_classifications`, `_log_ranked_news`) write to the same
    in-memory engine the test fixture is bound to.

    The conftest engine uses StaticPool, so commits via fresh sessions are
    visible to the original `test_db_session`.
    """
    test_factory = sessionmaker(
        bind=test_db_session.bind,
        autocommit=False,
        autoflush=False,
    )
    with patch("app.db.session.SessionLocal", test_factory):
        yield


def _extract_callback_data(send_message_mock) -> str:
    """Extract callback_data of the FIRST button from the most recent send_message call."""
    _args, kwargs = send_message_mock.call_args
    return kwargs["reply_markup"]["inline_keyboard"][0][0]["callback_data"]


def test_e2e_inbox_logging_hash_matches_button_hash(db_session):
    """Full pipeline: summarize_emails → memory log → button → parse → add_feedback."""
    from app.integrations.email_models import EmailMessage
    from app.modules.inbox.service import InboxService

    # Long ID (> 32 chars) forces to_callback_ref to apply md5 hashing.
    long_id = "msg_" + "a" * 60
    real_email = EmailMessage(
        id=long_id,
        sender="boss@example.com",
        subject="Reuniao amanha — confirma?",
        snippet="Por favor confirma sua presenca",
        priority="baixa",
        timestamp="2026-04-25T10:00:00",
        is_read=False,
    )

    mock_client = MagicMock()
    mock_client.list_recent_emails.return_value = [real_email]

    # Patch SessionLocal so _log_email_classifications writes to the test DB
    with _patched_session_local(db_session):
        result = InboxService(client=mock_client).summarize_emails()

    # Memory event was persisted with hashed reference_id
    memory_svc = MemoryService(db_session)
    expected_ref = to_callback_ref(long_id)
    events = memory_svc.get_recent_events(event_type="email_classified")
    assert len(events) == 1
    assert events[0].reference_id == expected_ref

    # Build buttons from the SAME data dict the orchestrator would receive
    bot = TelegramBot()
    bot.send_message = MagicMock(return_value={"ok": True})
    bot.send_inbox_items_with_feedback("chat", result)

    # The button must exist (top5 has the email)
    assert bot.send_message.call_count == 1, "Inbox top5 should produce one button row"

    cb_data = _extract_callback_data(bot.send_message)

    # Parse the callback as the webhook would
    parsed = _parse_feedback_callback(cb_data)
    assert parsed is not None, f"Callback was not parsable: {cb_data}"
    src, ref_from_button, sig = parsed

    # The hash on the button MUST match the hash in the DB
    assert ref_from_button == expected_ref

    # Feedback lookup must hit the event
    source, event_type = _FB_SRC_MAP[src]
    saved = memory_svc.add_feedback(
        ref_from_button, _FB_SIG_MAP[sig],
        source=source, event_type=event_type,
    )
    assert saved is True

    # And the feedback is persisted
    events_after = memory_svc.get_recent_events(event_type="email_classified")
    assert events_after[0].feedback == "positive"


def test_e2e_news_logging_hash_matches_button_hash(db_session):
    """Full pipeline: _log_ranked_news → memory log → button → parse → add_feedback.

    We bypass `summarize_news()` entirely because its date/scope/quality filters
    would block synthetic articles. The invariant under test is the hash symmetry
    between `_log_ranked_news` and `send_news_items_with_feedback`, both of which
    use `to_callback_ref` over (link or title).
    """
    from app.modules.briefing.news_service import _log_ranked_news

    # Long URL forces hashing.
    long_url = "https://economia.example.com/" + "x" * 200
    item = {
        "link": long_url,
        "title": "Mercado fecha em alta",
        "category": "macro",
        "score": 80,
        "score_reasons": ["palavra_chave_macro"],
        "priority": "high",
    }

    # Patch SessionLocal so _log_ranked_news writes to the test DB
    with _patched_session_local(db_session):
        _log_ranked_news([item])

    memory_svc = MemoryService(db_session)
    expected_ref = to_callback_ref(long_url)
    events = memory_svc.get_recent_events(event_type="news_ranked")
    assert len(events) == 1
    assert events[0].reference_id == expected_ref

    # Build buttons from the same item dict (post-strip equivalent)
    bot = TelegramBot()
    bot.send_message = MagicMock(return_value={"ok": True})
    bot.send_news_items_with_feedback("chat", {"items": [item]})

    assert bot.send_message.call_count == 1
    cb_data = _extract_callback_data(bot.send_message)

    parsed = _parse_feedback_callback(cb_data)
    assert parsed is not None
    src, ref_from_button, sig = parsed
    assert ref_from_button == expected_ref

    source, event_type = _FB_SRC_MAP[src]
    saved = memory_svc.add_feedback(
        ref_from_button, _FB_SIG_MAP[sig],
        source=source, event_type=event_type,
    )
    assert saved is True

    events_after = memory_svc.get_recent_events(event_type="news_ranked")
    assert events_after[0].feedback == "positive"


# ── Per-item resilience (ALTO-1 fix) ──────────────────────────────────────────

def test_send_inbox_continues_after_per_item_failure():
    """If item 0 raises during send, items 1-N must still be processed."""
    bot = TelegramBot()

    call_count = {"n": 0}

    def fail_first(*_args, **_kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("first item kaboom")
        return {"ok": True}

    bot.send_message = MagicMock(side_effect=fail_first)

    inbox_data = {
        "top5": [
            {"id": "msg_1", "subject": "first",  "sender": "a@b.com", "priority": "alta"},
            {"id": "msg_2", "subject": "second", "sender": "c@d.com", "priority": "media"},
            {"id": "msg_3", "subject": "third",  "sender": "e@f.com", "priority": "baixa"},
        ]
    }
    bot.send_inbox_items_with_feedback("123", inbox_data)

    # All three items reached send_message — proves the loop did NOT abort
    assert bot.send_message.call_count == 3


def test_send_news_continues_after_per_item_failure():
    """If item 0 raises during send, items 1-N must still be processed."""
    bot = TelegramBot()

    call_count = {"n": 0}

    def fail_first(*_args, **_kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("first item kaboom")
        return {"ok": True}

    bot.send_message = MagicMock(side_effect=fail_first)

    news_data = {
        "items": [
            {"link": "https://e.com/a", "title": "A", "category": "macro",  "priority": "high"},
            {"link": "https://e.com/b", "title": "B", "category": "mercado", "priority": "medium"},
            {"link": "https://e.com/c", "title": "C", "category": "politica", "priority": "high"},
        ]
    }
    bot.send_news_items_with_feedback("chat", news_data)

    assert bot.send_message.call_count == 3


# ── Webhook regression (real POST through TestClient) ────────────────────────

def _msg_update(text: str, user_id: int = 12345) -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "from": {"id": user_id, "first_name": "Test"},
            "chat": {"id": user_id, "type": "private"},
            "date": 1234567890,
            "text": text,
        },
    }


def _cb_update(data: str, user_id: int = 12345, cb_id: str = "cbq_1") -> dict:
    return {
        "update_id": 1,
        "callback_query": {
            "id": cb_id,
            "from": {"id": user_id, "first_name": "Test"},
            "message": {
                "message_id": 1,
                "chat": {"id": user_id, "type": "private"},
            },
            "data": data,
        },
    }


def test_webhook_finance_command_does_not_call_feedback_helpers(client, db_session):
    """A `/finance` message must route through Orchestrator, never touch feedback helpers."""
    with patch("app.api.rest.routes.TelegramBot") as MockBot, \
         patch("app.api.rest.routes.Orchestrator") as MockOrch:
        bot = MockBot.return_value
        bot.parse_update.return_value = {
            "type": "message",
            "user_id": "12345",
            "chat_id": "12345",
            "text": "/finance",
        }
        bot.is_authorized.return_value = True

        orch = MockOrch.return_value
        orch.handle_request.return_value = {
            "intent": "get_finance_summary",
            "confidence": 1.0,
            "success": True,
            "data": {},
            "message": "Resumo financeiro",
        }

        resp = client.post("/telegram/webhook", json=_msg_update("/finance"))

    assert resp.status_code == 200
    bot.send_inbox_items_with_feedback.assert_not_called()
    bot.send_news_items_with_feedback.assert_not_called()
    # The orchestrator was reached and its message was sent
    orch.handle_request.assert_called_once()
    bot.send_message.assert_called()


def test_webhook_fin_menu_callback_does_not_route_to_feedback(client, db_session):
    """`fin:menu` must hit the finance menu handler, not the feedback handler."""
    with patch("app.api.rest.routes.TelegramBot") as MockBot:
        bot = MockBot.return_value
        bot.parse_update.return_value = {
            "type": "callback",
            "user_id": "12345",
            "chat_id": "12345",
            "text": "fin:menu",
            "callback_query_id": "cbq_fin",
        }
        bot.is_authorized.return_value = True
        bot.build_finance_menu.return_value = {"inline_keyboard": [[]]}

        resp = client.post("/telegram/webhook", json=_cb_update("fin:menu", cb_id="cbq_fin"))

    assert resp.status_code == 200
    # Generic spinner-removal answer was called (without text)
    bot.answer_callback_query.assert_called_once_with("cbq_fin")
    # Feedback rendering was NOT invoked
    bot.send_inbox_items_with_feedback.assert_not_called()
    bot.send_news_items_with_feedback.assert_not_called()
    # Finance menu was sent
    bot.send_message.assert_called()
    # Finance menu builder was used (not feedback keyboard)
    bot.build_finance_menu.assert_called_once()


def test_webhook_fb_callback_routes_to_feedback_handler(client, db_session):
    """`fb:e:<ref>:pos` must hit the feedback handler and persist."""
    # Seed an event so add_feedback returns True
    svc = MemoryService(db_session)
    svc.log_event("email_classified", "email", "wh_test_ref", {"category": "action"})

    with patch("app.api.rest.routes.TelegramBot") as MockBot:
        bot = MockBot.return_value
        bot.parse_update.return_value = {
            "type": "callback",
            "user_id": "12345",
            "chat_id": "12345",
            "text": "fb:e:wh_test_ref:pos",
            "callback_query_id": "cbq_fb",
        }
        bot.is_authorized.return_value = True

        resp = client.post(
            "/telegram/webhook",
            json=_cb_update("fb:e:wh_test_ref:pos", cb_id="cbq_fb"),
        )

    assert resp.status_code == 200
    # Feedback handler answered with the success toast
    bot.answer_callback_query.assert_called_once_with("cbq_fb", "Feedback registrado.")
    # Feedback handler short-circuits — orchestrator/inbox/news rendering NOT touched
    bot.send_inbox_items_with_feedback.assert_not_called()
    bot.send_news_items_with_feedback.assert_not_called()
    bot.send_message.assert_not_called()

    # And the feedback was persisted
    events = svc.get_recent_events(event_type="email_classified")
    assert events[0].feedback == "positive"
