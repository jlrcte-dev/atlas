"""Intent classification layer for Atlas AI Assistant.

Rule-based implementation structured for future LLM upgrade:
swap classify() body to call Claude with tool_use, keeping
the same ClassifiedIntent return type.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum


class Intent(StrEnum):
    GET_INBOX_SUMMARY = "get_inbox_summary"
    GET_CALENDAR = "get_calendar"
    CREATE_EVENT = "create_event"
    GET_NEWS = "get_news"
    GET_DAILY_BRIEFING = "get_daily_briefing"
    APPROVE_ACTION = "approve_action"
    REJECT_ACTION = "reject_action"
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ClassifiedIntent:
    intent: Intent
    confidence: float
    params: dict[str, str] = field(default_factory=dict)


# ── Command mapping (Telegram /commands) ──────────────────────────

_COMMAND_MAP: dict[str, Intent] = {
    "/inbox": Intent.GET_INBOX_SUMMARY,
    "/email": Intent.GET_INBOX_SUMMARY,
    "/emails": Intent.GET_INBOX_SUMMARY,
    "/calendar": Intent.GET_CALENDAR,
    "/agenda": Intent.GET_CALENDAR,
    "/news": Intent.GET_NEWS,
    "/noticias": Intent.GET_NEWS,
    "/briefing": Intent.GET_DAILY_BRIEFING,
    "/resumo": Intent.GET_DAILY_BRIEFING,
    "/approve": Intent.APPROVE_ACTION,
    "/aprovar": Intent.APPROVE_ACTION,
    "/reject": Intent.REJECT_ACTION,
    "/rejeitar": Intent.REJECT_ACTION,
    "/help": Intent.HELP,
    "/ajuda": Intent.HELP,
}

# ── Pattern definitions ───────────────────────────────────────────
# Order matters: more specific intents first.
# Each entry: (Intent, multi-word phrases, single keywords)

_INTENT_PATTERNS: list[tuple[Intent, list[str], list[str]]] = [
    (
        Intent.CREATE_EVENT,
        [
            "criar evento",
            "agendar reuniao",
            "agendar reunião",
            "marcar reuniao",
            "marcar reunião",
            "marcar call",
            "criar reuniao",
            "criar reunião",
            "novo evento",
        ],
        [
            "agendar",
            "schedule",
        ],
    ),
    (
        Intent.APPROVE_ACTION,
        [
            "aprovar acao",
            "aprovar ação",
        ],
        [
            "aprovar",
            "approve",
            "confirmar",
            "confirm",
        ],
    ),
    (
        Intent.REJECT_ACTION,
        [
            "rejeitar acao",
            "rejeitar ação",
        ],
        [
            "rejeitar",
            "reject",
            "negar",
        ],
    ),
    (
        Intent.GET_DAILY_BRIEFING,
        [
            "resumo do dia",
            "resumo diario",
            "resumo diário",
            "daily briefing",
            "meu briefing",
        ],
        [
            "briefing",
        ],
    ),
    (
        Intent.GET_INBOX_SUMMARY,
        [
            "meus emails",
            "minha inbox",
            "caixa de entrada",
        ],
        [
            "email",
            "emails",
            "inbox",
            "caixa",
            "mensagens",
            "correio",
        ],
    ),
    (
        Intent.GET_CALENDAR,
        [
            "minha agenda",
            "meus compromissos",
        ],
        [
            "agenda",
            "calendar",
            "calendário",
            "calendario",
            "compromisso",
            "compromissos",
            "reunião",
            "reuniao",
            "eventos",
        ],
    ),
    (
        Intent.GET_NEWS,
        [
            "ultimas noticias",
            "últimas notícias",
        ],
        [
            "noticia",
            "noticias",
            "notícia",
            "notícias",
            "news",
            "rss",
            "manchete",
            "manchetes",
        ],
    ),
    (
        Intent.HELP,
        [],
        [
            "ajuda",
            "help",
            "comandos",
            "commands",
        ],
    ),
]


class IntentClassifier:
    """Rule-based intent classifier.

    To upgrade to LLM: replace the body of classify() with a Claude
    tool_use call. The return type stays ClassifiedIntent.
    """

    def classify(self, message: str) -> ClassifiedIntent:
        lowered = message.lower().strip()
        params = _extract_params(lowered)

        # Priority 1: Telegram slash-commands
        if lowered.startswith("/"):
            return _classify_command(lowered, params)

        # Priority 2: Multi-word phrases (high specificity)
        for intent, phrases, _kw in _INTENT_PATTERNS:
            for phrase in phrases:
                if phrase in lowered:
                    return ClassifiedIntent(intent=intent, confidence=0.9, params=params)

        # Priority 3: Single-keyword scoring
        scores: dict[Intent, int] = {}
        for intent, _phrases, keywords in _INTENT_PATTERNS:
            for kw in keywords:
                if re.search(rf"\b{re.escape(kw)}\b", lowered):
                    scores[intent] = scores.get(intent, 0) + 1

        if scores:
            best = max(scores, key=lambda k: scores[k])
            confidence = min(0.5 + scores[best] * 0.15, 0.85)
            return ClassifiedIntent(intent=best, confidence=confidence, params=params)

        return ClassifiedIntent(intent=Intent.UNKNOWN, confidence=0.0, params=params)


# ── Private helpers ───────────────────────────────────────────────


def _classify_command(message: str, params: dict[str, str]) -> ClassifiedIntent:
    parts = message.split()
    command = parts[0].split("@")[0]  # strip @botname suffix

    if command == "/start":
        return ClassifiedIntent(
            intent=Intent.HELP,
            confidence=1.0,
            params={**params, "welcome": "true"},
        )

    intent = _COMMAND_MAP.get(command, Intent.UNKNOWN)

    # Extract ID from command args: /approve 42
    if len(parts) > 1 and parts[1].isdigit():
        params = {**params, "action_id": parts[1]}

    return ClassifiedIntent(intent=intent, confidence=1.0, params=params)


def _extract_params(message: str) -> dict[str, str]:
    params: dict[str, str] = {}
    match = re.search(r"(?:#|nº|id\s*)(\d+)", message)
    if match:
        params["action_id"] = match.group(1)
    return params
