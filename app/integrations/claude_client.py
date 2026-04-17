"""Claude API client for Atlas AI Assistant.

Provides intent classification and natural language response generation.
All methods fail gracefully: returns None on any error so the caller
can fall back to rule-based logic without disruption.
"""

from __future__ import annotations

import json

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("integrations.claude")

# ── Tool definition for structured intent classification ──────────

_CLASSIFY_TOOL: dict = {
    "name": "classify_intent",
    "description": (
        "Classifica a intenção do usuário no Atlas AI Assistant. "
        "Use os intents disponíveis para mapear o pedido em português ou inglês."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": [
                    "get_inbox_summary",
                    "get_calendar",
                    "create_event",
                    "get_news",
                    "get_daily_briefing",
                    "approve_action",
                    "reject_action",
                    "help",
                    "unknown",
                ],
                "description": "A intenção classificada do usuário.",
            },
            "confidence": {
                "type": "number",
                "description": "Confiança da classificação, de 0.0 a 1.0.",
            },
            "action_id": {
                "type": "string",
                "description": (
                    "ID numérico da ação para intents approve_action ou reject_action, "
                    "se presente na mensagem (ex: 'aprovar #42' → '42')."
                ),
            },
        },
        "required": ["intent", "confidence"],
    },
}

_SYSTEM_CLASSIFY = (
    "Você é o classificador de intenções do Atlas AI Assistant, "
    "um hub operacional pessoal. "
    "Dado o texto do usuário, use o tool classify_intent para classificar a intenção. "
    "Seja preciso. Use confidence baixo quando houver ambiguidade."
)

_SYSTEM_GENERATE = (
    "Você é o Atlas AI Assistant, hub operacional pessoal. "
    "Dado um contexto estruturado em JSON, gere uma resposta concisa em português brasileiro. "
    "Seja direto e útil. Sem markdown excessivo. Máximo de 3 parágrafos curtos."
)


class ClaudeClient:
    """Thin wrapper around the Anthropic Messages API.

    Designed for graceful degradation: every public method returns None
    when Claude is unavailable, allowing rule-based fallback.
    """

    def __init__(self) -> None:
        self._client = None  # lazy init — avoids import cost if unused

    def _get_client(self):
        """Return an authenticated Anthropic client, or None if unavailable."""
        if self._client is None:
            if not settings.anthropic_api_key:
                return None
            try:
                from anthropic import Anthropic

                self._client = Anthropic(api_key=settings.anthropic_api_key)
            except ImportError:
                logger.warning("anthropic package not installed — Claude features disabled")
                return None
        return self._client

    def classify_intent(self, message: str) -> dict | None:
        """Classify user intent using Claude tool_use.

        Returns dict with keys:
          - intent (str): one of the known Intent values
          - confidence (float): 0.0-1.0
          - params (dict): optional extracted params (e.g. action_id)

        Returns None on any failure — caller must fall back to rule-based.
        Timeout: 3 seconds (fast path for classification).
        """
        client = self._get_client()
        if client is None:
            return None

        try:
            response = client.messages.create(
                model=settings.claude_model,
                max_tokens=200,
                system=_SYSTEM_CLASSIFY,
                tools=[_CLASSIFY_TOOL],
                tool_choice={"type": "tool", "name": "classify_intent"},
                messages=[{"role": "user", "content": message}],
                timeout=3.0,
            )
            for block in response.content:
                if block.type == "tool_use":
                    data = block.input
                    params: dict[str, str] = {}
                    if data.get("action_id"):
                        params["action_id"] = str(data["action_id"])
                    return {
                        "intent": data.get("intent", "unknown"),
                        "confidence": float(data.get("confidence", 0.85)),
                        "params": params,
                    }
        except Exception:
            logger.debug("Claude classify_intent failed — using rule-based fallback")
        return None

    def generate_response(self, context: dict) -> str | None:
        """Generate a natural language response from structured context.

        Args:
            context: dict with any structured data (agenda, inbox summary, etc.)

        Returns the generated text, or None on failure.
        Timeout: 8 seconds.
        """
        client = self._get_client()
        if client is None:
            return None

        try:
            payload = json.dumps(context, ensure_ascii=False, default=str)
            response = client.messages.create(
                model=settings.claude_model,
                max_tokens=500,
                system=_SYSTEM_GENERATE,
                messages=[{"role": "user", "content": payload}],
                timeout=8.0,
            )
            if response.content and response.content[0].type == "text":
                return response.content[0].text
        except Exception:
            logger.debug("Claude generate_response failed — using structured fallback")
        return None
