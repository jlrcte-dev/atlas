"""Telegram Bot integration.

Uses httpx to call the Telegram Bot API directly.
No extra dependency required — httpx is already in the stack.
"""

from __future__ import annotations

import html
import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("integrations.telegram")

_API_BASE = "https://api.telegram.org/bot{token}"
_BLOCK_HARD_LIMIT = 4096  # Telegram rejects messages above this length
_BLOCK_WARN_SIZE = 3500   # warn early before hitting the hard limit


def _split_block_by_lines(block: str) -> list[str]:
    """Split an oversized block into line-safe chunks, each ≤ _BLOCK_HARD_LIMIT chars.

    All HTML tags in our blocks open and close within the same line, so splitting
    at line boundaries always produces valid HTML — no regex or tag-parsing needed.
    """
    if len(block) <= _BLOCK_HARD_LIMIT:
        return [block]

    lines = block.split("\n")
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        line_cost = len(line) + 1  # +1 for the rejoining \n
        if current and current_len + line_cost > _BLOCK_HARD_LIMIT:
            chunks.append("\n".join(current))
            current = [line]
            current_len = line_cost
        else:
            current.append(line)
            current_len += line_cost

    if current:
        chunks.append("\n".join(current))

    return chunks


def esc(text: str) -> str:
    """Escape content for Telegram HTML parse_mode — must be called on ALL dynamic content."""
    return html.escape(str(text))


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
            "parse_mode": "HTML",
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

    # ── Proactive briefing ────────────────────────────────────────

    @staticmethod
    def format_briefing_blocks(briefing: dict) -> list[str]:
        """Build 2 HTML blocks from a BriefingService.run_daily_briefing() result.

        Block 1: Agenda + free slots + inbox
        Block 2: News summary + curated items

        All dynamic content is escaped. Blocks are built to stay well under the
        4096-char Telegram limit; a warning is logged if one approaches 3500 chars.
        No regex or HTML parsing is used for truncation.
        """
        sections = briefing.get("sections", {})
        cal = sections.get("calendar", {})
        free_slots = sections.get("free_slots", [])
        inbox = sections.get("inbox", {})
        news = sections.get("news", {})

        # ── Block 1: Agenda + free slots + inbox ──────────────────
        b1: list[str] = ["<b>📋 Briefing Diario</b>", ""]

        b1.append(f"<b>📅 Agenda</b> — {esc(cal.get('total', 0))} compromisso(s)")
        for evt in cal.get("events", []):
            b1.append(f"• {esc(evt.get('start', ''))} | {esc(evt.get('title', ''))}")

        if free_slots:
            b1.append(f"\n<b>⏰ Horarios livres</b> — {len(free_slots)} slot(s)")
            for slot in free_slots[:3]:
                b1.append(
                    f"• {esc(slot.get('start', ''))}-{esc(slot.get('end', ''))}"
                    f" ({esc(slot.get('duration_minutes', ''))}min)"
                )

        b1.append(f"\n<b>📥 Inbox</b>")
        total_emails = inbox.get("total", 0)
        unread_count = inbox.get("unread", 0)
        nl_count = inbox.get("newsletter_count", 0)
        high_count = inbox.get("high_priority", 0)
        medium_count = inbox.get("medium_priority", 0)
        low_count = inbox.get("low_priority", 0)
        b1.append(
            f"📊 {esc(total_emails)} analisados · "
            f"{esc(unread_count)} não lidos · "
            f"{esc(nl_count)} newsletters"
        )
        b1.append(
            f"🔴 {esc(high_count)} alta · "
            f"🟡 {esc(medium_count)} média · "
            f"⚪ {esc(low_count)} baixa"
        )
        top5 = inbox.get("top5", [])
        if top5:
            b1.append("\n<b>📌 Top 5 prioritários</b>")
            _PRIORITY_ICON = {"alta": "🔴", "media": "🟡", "baixa": "⚪"}
            for item in top5:
                icon = _PRIORITY_ICON.get(item.get("priority", ""), "⚪")
                raw_sender = item.get("sender", "")
                # Show display name when available ("Name <email>"), else local-part
                if "<" in raw_sender:
                    display_sender = raw_sender.split("<")[0].strip() or raw_sender.split("<")[1].rstrip(">").strip()
                elif "@" in raw_sender:
                    display_sender = raw_sender.split("@")[0]
                else:
                    display_sender = raw_sender
                raw_subj = item.get("subject", "")
                short_subj = (raw_subj[:57] + "…") if len(raw_subj) > 60 else raw_subj
                b1.append(
                    f"{icon} <b>{esc(short_subj)}</b>\n"
                    f"   De: {esc(display_sender)} · {esc(item.get('short_reason', ''))}"
                )
        else:
            b1.append(esc(inbox.get("summary", "")))

        block1 = "\n".join(b1)

        # ── Block 2: News ─────────────────────────────────────────
        # news["summary"] already contains the "📰 Radar de Noticias" header
        b2: list[str] = [esc(news.get("summary", "")), ""]
        for item in news.get("items", []):
            icon = "🔴" if item.get("priority") == "high" else "🟡"
            b2.append(
                f"{icon} {esc(item.get('title', ''))}"
                f" <i>[{esc(item.get('category', ''))}]</i>"
            )

        block2 = "\n".join(b2)

        return [block1, block2]

    def send_briefing(self, chat_id: str | int, briefing: dict) -> dict:
        """Send briefing as independent HTML blocks. Continues on per-block failure.

        Oversized blocks are split by line boundary (HTML-safe) before sending.
        Per-block failures are logged and never crash the application.
        """
        blocks = self.format_briefing_blocks(briefing)
        sent = failed = 0

        for idx, block in enumerate(blocks, 1):
            if len(block) > _BLOCK_WARN_SIZE:
                logger.warning(
                    "Briefing block %d is %d chars — approaching Telegram limit",
                    idx, len(block),
                )

            sub_blocks = _split_block_by_lines(block)
            if len(sub_blocks) > 1:
                logger.warning(
                    "Block %d exceeded limit (%d chars) — split into %d sub-blocks",
                    idx, len(block), len(sub_blocks),
                )

            for sub_idx, sub_block in enumerate(sub_blocks, 1):
                label = f"{idx}.{sub_idx}" if len(sub_blocks) > 1 else str(idx)
                try:
                    result = self.send_message(chat_id, sub_block)
                    if result.get("ok"):
                        sent += 1
                    else:
                        failed += 1
                        logger.error(
                            "Telegram rejected briefing block %s: %s",
                            label, result.get("description"),
                        )
                except Exception as exc:
                    failed += 1
                    logger.error("Unexpected error sending briefing block %s: %s", label, exc)

        return {"sent": sent, "failed": failed, "total_blocks": sent + failed}

    @staticmethod
    def build_main_menu() -> dict:
        """Build the main navigation inline keyboard."""
        return {
            "inline_keyboard": [
                [
                    {"text": "💰 Finanças", "callback_data": "fin:menu"},
                ],
                [
                    {"text": "📥 Inbox", "callback_data": "cmd:/inbox"},
                    {"text": "📅 Agenda", "callback_data": "cmd:/agenda"},
                ],
                [
                    {"text": "📰 Noticias", "callback_data": "cmd:/news"},
                    {"text": "📑 Briefing", "callback_data": "cmd:/briefing"},
                ],
                [
                    {"text": "⏳ Pendencias", "callback_data": "cmd:/pending"},
                ],
            ]
        }

    @staticmethod
    def build_finance_menu() -> dict:
        """Build the Finance module inline keyboard."""
        return {
            "inline_keyboard": [
                [{"text": "📊 Resumo do mês", "callback_data": "fin:sum"}],
                [{"text": "➕ Como lançar despesa", "callback_data": "fin:help_exp"}],
                [{"text": "➕ Como lançar receita", "callback_data": "fin:help_inc"}],
                [{"text": "🏦 Como atualizar saldo", "callback_data": "fin:help_bal"}],
                [{"text": "⬅️ Voltar", "callback_data": "fin:back"}],
            ]
        }

    @staticmethod
    def build_approval_keyboard(draft_id: int) -> dict:
        """Build an inline keyboard with Approve / Reject buttons.

        callback_data uses short prefixes (apprv/rejct) to stay well under the 64-byte limit.
        """
        return {
            "inline_keyboard": [
                [
                    {"text": "✅ Aprovar", "callback_data": f"apprv:{draft_id}"},
                    {"text": "❌ Rejeitar", "callback_data": f"rejct:{draft_id}"},
                ]
            ]
        }

    # ── Feedback (Memory loop) ───────────────────────────────────

    @staticmethod
    def build_feedback_keyboard(src: str, ref: str) -> dict:
        """Build inline keyboard with feedback buttons for a single item.

        Format `fb:<src>:<ref>:<sig>` is kept short to stay well under
        Telegram's 64-byte callback_data limit. `ref` must already be a short
        identifier (≤ 32 chars) — see `app.modules.memory.utils.to_callback_ref`.
        """
        return {
            "inline_keyboard": [
                [
                    {"text": "👍 Relevante",   "callback_data": f"fb:{src}:{ref}:pos"},
                    {"text": "👎 Irrelevante", "callback_data": f"fb:{src}:{ref}:neg"},
                    {"text": "⭐ Prioridade",  "callback_data": f"fb:{src}:{ref}:imp"},
                ]
            ]
        }

    def send_inbox_items_with_feedback(self, chat_id: str | int, inbox_data: dict) -> None:
        """Send each top-5 inbox item as an individual message with feedback buttons.

        Per-item fail-safe — a malformed item is logged and skipped so that
        remaining items still reach the user.
        """
        try:
            from app.modules.memory.utils import to_callback_ref
        except Exception as exc:
            logger.warning("send_inbox_items_with_feedback: setup falhou: %s", exc)
            return

        top5 = inbox_data.get("top5") or []
        if not top5:
            return

        priority_icon = {"alta": "🔴", "media": "🟡", "baixa": "⚪"}
        for item in top5:
            try:
                raw_id = item.get("id", "")
                ref = to_callback_ref(raw_id) if raw_id else ""
                if not ref:
                    continue

                icon = priority_icon.get(item.get("priority", ""), "⚪")
                subject = item.get("subject", "") or "(sem assunto)"
                short_subj = (subject[:57] + "…") if len(subject) > 60 else subject
                sender_raw = item.get("sender", "") or ""
                if "<" in sender_raw:
                    sender = sender_raw.split("<")[0].strip() or sender_raw
                elif "@" in sender_raw:
                    sender = sender_raw.split("@")[0]
                else:
                    sender = sender_raw

                short_reason = item.get("short_reason", "") or ""
                tail = f" · {esc(short_reason)}" if short_reason else ""
                text = (
                    f"{icon} <b>{esc(short_subj)}</b>\n"
                    f"De: {esc(sender)}{tail}"
                )
                self.send_message(
                    chat_id, text,
                    reply_markup=self.build_feedback_keyboard("e", ref),
                )
            except Exception as exc:
                logger.warning(
                    "send_inbox_items_with_feedback: item %s falhou: %s",
                    item.get("id", "?"), exc,
                )
                continue

    def send_news_items_with_feedback(self, chat_id: str | int, news_data: dict) -> None:
        """Send each curated news item as an individual message with feedback buttons.

        Per-item fail-safe — a malformed item is logged and skipped so that
        remaining items still reach the user.
        """
        try:
            from app.modules.memory.utils import to_callback_ref
        except Exception as exc:
            logger.warning("send_news_items_with_feedback: setup falhou: %s", exc)
            return

        items = (news_data.get("items") or [])[:5]
        if not items:
            return

        for item in items:
            try:
                raw = item.get("link") or item.get("title", "") or ""
                ref = to_callback_ref(raw) if raw else ""
                if not ref:
                    continue

                icon = "🔴" if item.get("priority") == "high" else "🟡"
                title = item.get("title", "") or "(sem titulo)"
                short_title = (title[:77] + "…") if len(title) > 80 else title
                category = item.get("category", "") or ""
                cat_tag = f" <i>[{esc(category)}]</i>" if category else ""
                text = f"{icon} <b>{esc(short_title)}</b>{cat_tag}"
                self.send_message(
                    chat_id, text,
                    reply_markup=self.build_feedback_keyboard("n", ref),
                )
            except Exception as exc:
                logger.warning(
                    "send_news_items_with_feedback: item %s falhou: %s",
                    item.get("link") or item.get("title", "?"), exc,
                )
                continue
