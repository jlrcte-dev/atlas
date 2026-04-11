"""Telegram Bot integration.

Uses httpx to call the Telegram Bot API directly.
No extra dependency required — httpx is already in the stack.
"""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("integrations.telegram")

_API_BASE = "https://api.telegram.org/bot{token}"


class TelegramBot:
    """Telegram Bot adapter for sending/receiving messages."""

    def __init__(self) -> None:
        self.token = settings.telegram_bot_token
        self.base_url = _API_BASE.format(token=self.token)
        self.allowed_user_id = settings.telegram_allowed_user_id
        self.enabled = bool(self.token)

    # ── Auth ──────────────────────────────────────────────────────

    def is_authorized(self, user_id: str | int) -> bool:
        if not self.allowed_user_id:
            return True  # no restriction configured
        return str(user_id) == self.allowed_user_id

    # ── Send ──────────────────────────────────────────────────────

    def send_message(
        self,
        chat_id: str | int,
        text: str,
        reply_markup: dict | None = None,
    ) -> dict:
        if not self.enabled:
            logger.warning("Telegram bot not configured — message not sent")
            return {"ok": False, "description": "Bot not configured"}

        payload: dict = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            resp = httpx.post(
                f"{self.base_url}/sendMessage",
                json=payload,
                timeout=10,
            )
            result: dict = resp.json()
            return result
        except httpx.HTTPError as exc:
            logger.error("Failed to send Telegram message: %s", exc)
            return {"ok": False, "description": str(exc)}

    def answer_callback_query(
        self,
        callback_query_id: str,
        text: str = "",
    ) -> dict:
        if not self.enabled:
            return {"ok": False}

        try:
            resp = httpx.post(
                f"{self.base_url}/answerCallbackQuery",
                json={"callback_query_id": callback_query_id, "text": text},
                timeout=10,
            )
            result: dict = resp.json()
            return result
        except httpx.HTTPError as exc:
            logger.error("Failed to answer callback: %s", exc)
            return {"ok": False, "description": str(exc)}

    # ── Parse incoming updates ────────────────────────────────────

    @staticmethod
    def parse_update(update: dict) -> dict | None:
        """Extract relevant fields from a Telegram update payload.

        Returns None if the update type is unsupported.
        """
        if "message" in update:
            msg = update["message"]
            return {
                "type": "message",
                "user_id": str(msg["from"]["id"]),
                "chat_id": str(msg["chat"]["id"]),
                "text": msg.get("text", ""),
            }

        if "callback_query" in update:
            cb = update["callback_query"]
            return {
                "type": "callback",
                "user_id": str(cb["from"]["id"]),
                "chat_id": str(cb["message"]["chat"]["id"]),
                "text": cb.get("data", ""),
                "callback_query_id": cb["id"],
            }

        return None

    # ── UI helpers ────────────────────────────────────────────────

    @staticmethod
    def build_approval_keyboard(draft_id: int) -> dict:
        """Build an inline keyboard with Approve / Reject buttons."""
        return {
            "inline_keyboard": [
                [
                    {"text": "Aprovar", "callback_data": f"approve:{draft_id}"},
                    {"text": "Rejeitar", "callback_data": f"reject:{draft_id}"},
                ]
            ]
        }

    @staticmethod
    def format_message(text: str) -> dict:
        """Legacy helper — kept for backward compat."""
        return {"text": text}
