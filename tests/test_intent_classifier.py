"""Tests for the intent classification layer."""

from app.orchestrator.intent_classifier import Intent, IntentClassifier


def _classify(msg: str) -> Intent:
    return IntentClassifier().classify(msg).intent


# ── Keyword-based classification ──────────────────────────────────


def test_classify_inbox_keyword():
    assert _classify("me mostra meus emails") == Intent.GET_INBOX_SUMMARY


def test_classify_inbox_phrase():
    assert _classify("qual o resumo da minha inbox?") == Intent.GET_INBOX_SUMMARY


def test_classify_calendar_keyword():
    assert _classify("qual minha agenda hoje?") == Intent.GET_CALENDAR


def test_classify_calendar_compromisso():
    assert _classify("tenho algum compromisso?") == Intent.GET_CALENDAR


def test_classify_news_keyword():
    assert _classify("tem alguma noticia importante?") == Intent.GET_NEWS


def test_classify_briefing_phrase():
    assert _classify("me da o resumo do dia") == Intent.GET_DAILY_BRIEFING


def test_classify_create_event_phrase():
    assert _classify("criar evento amanha 10h") == Intent.CREATE_EVENT


def test_classify_create_event_agendar():
    assert _classify("agendar reuniao com o time") == Intent.CREATE_EVENT


# ── Approval intents ──────────────────────────────────────────────


def test_classify_approve_with_hash_id():
    c = IntentClassifier()
    result = c.classify("aprovar #42")
    assert result.intent == Intent.APPROVE_ACTION
    assert result.params.get("action_id") == "42"


def test_classify_reject_with_hash_id():
    c = IntentClassifier()
    result = c.classify("rejeitar acao #7")
    assert result.intent == Intent.REJECT_ACTION
    assert result.params.get("action_id") == "7"


# ── Command classification ────────────────────────────────────────


def test_command_inbox():
    c = IntentClassifier()
    result = c.classify("/inbox")
    assert result.intent == Intent.GET_INBOX_SUMMARY
    assert result.confidence == 1.0


def test_command_agenda():
    assert _classify("/agenda") == Intent.GET_CALENDAR


def test_command_news():
    assert _classify("/news") == Intent.GET_NEWS


def test_command_briefing():
    assert _classify("/briefing") == Intent.GET_DAILY_BRIEFING


def test_command_approve_with_arg():
    c = IntentClassifier()
    result = c.classify("/approve 42")
    assert result.intent == Intent.APPROVE_ACTION
    assert result.params.get("action_id") == "42"


def test_command_reject_with_arg():
    c = IntentClassifier()
    result = c.classify("/reject 7")
    assert result.intent == Intent.REJECT_ACTION
    assert result.params.get("action_id") == "7"


def test_command_help():
    assert _classify("/help") == Intent.HELP


def test_command_start_maps_to_help():
    c = IntentClassifier()
    result = c.classify("/start")
    assert result.intent == Intent.HELP
    assert result.params.get("welcome") == "true"


# ── Unknown ───────────────────────────────────────────────────────


def test_classify_unknown():
    c = IntentClassifier()
    result = c.classify("abcxyz foo bar")
    assert result.intent == Intent.UNKNOWN
    assert result.confidence == 0.0
