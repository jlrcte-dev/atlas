"""Inbox Copilot service.

Reads, classifies, and summarizes emails via the active email provider client.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger, log_action
from app.integrations.base_email_client import BaseEmailClient
from app.integrations.email_classifier import (
    EmailClassification,
    build_short_reason,
    classify_email,
)
from app.integrations.email_models import EmailMessage, email_to_dict
from app.integrations.gmail_client import GmailClient

logger = get_logger("services.inbox")


@dataclass
class InboxAdjustment:
    """Internal-only carrier of adaptive scoring state for one email.

    Held in a service-local dict during summarize_emails; never serialized to
    the public payload. Fields:
      base       — base score from EmailClassification.score (cast to float)
      adjustment — feedback-derived delta from compute_memory_adjustment
      reason     — feedback label that produced the adjustment, or None
      final      — base + adjustment (used as the ranking key)
    """
    base: float
    adjustment: float
    reason: Optional[str]
    final: float


_FALLBACK_CLASSIFICATION = EmailClassification(
    category="update",
    priority="baixa",
    requires_response=False,
    has_deadline=False,
    is_follow_up=False,
    is_opportunity=False,
    reason_codes=["classification_error"],
    score=0,
    score_reasons=[],
)


_PRIORITY_ORDER: dict[str, int] = {"alta": 0, "media": 1, "baixa": 2}


def _compute_email_adjustments(
    emails: list[EmailMessage],
    classifications: dict[str, EmailClassification],
) -> dict[str, "InboxAdjustment"]:
    """Compute memory adjustments for each email. Fail-safe — never raises.

    Returns a dict keyed by email.id with InboxAdjustment(base, adjustment, reason,
    final). Items missing from the dict default to neutral on lookup. Opens its
    own DB session (out-of-band, like _log_email_classifications) so any failure
    is isolated from the main inbox pipeline.

    Per-item logs at DEBUG; one INFO line summarizing applied count per batch.
    """
    if not emails:
        return {}
    try:
        from app.db.session import SessionLocal
        from app.modules.memory.scoring import compute_memory_adjustment
        from app.modules.memory.utils import to_callback_ref
    except Exception as exc:
        logger.warning("AdaptiveScore: imports falharam (inbox): %s", exc)
        return {}

    result: dict[str, InboxAdjustment] = {}
    applied = 0
    db = None
    try:
        db = SessionLocal()
        for email in emails:
            clf = classifications.get(email.id)
            base = float(clf.score) if clf is not None else 0.0
            try:
                ref = to_callback_ref(email.id) if email.id else ""
                if not ref:
                    result[email.id] = InboxAdjustment(base, 0.0, None, base)
                    continue
                adj = compute_memory_adjustment(
                    "email", ref, base, db_session=db
                )
                final = base + adj.adjustment
                result[email.id] = InboxAdjustment(base, adj.adjustment, adj.reason, final)
                if adj.adjustment != 0.0:
                    applied += 1
                    sign = "+" if adj.adjustment > 0 else ""
                    logger.debug(
                        "[AdaptiveScore] src=email ref=%s base=%.1f adj=%s%.1f final=%.1f",
                        ref, base, sign, adj.adjustment, final,
                    )
            except Exception as exc:
                logger.warning(
                    "AdaptiveScore: falha por item (email=%s): %s", email.id, exc
                )
                result[email.id] = InboxAdjustment(base, 0.0, None, base)
    except Exception as exc:
        logger.warning("AdaptiveScore: sessão DB falhou (inbox): %s", exc)
        # Best-effort neutral fill
        for email in emails:
            if email.id not in result:
                clf = classifications.get(email.id)
                base = float(clf.score) if clf is not None else 0.0
                result[email.id] = InboxAdjustment(base, 0.0, None, base)
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:  # pragma: no cover — defensive
                pass

    if applied:
        logger.info(
            "Applied adaptive scoring to %d/%d items (Inbox)", applied, len(emails)
        )
    return result


def _build_top5(
    emails: list[EmailMessage],
    classifications: dict[str, EmailClassification],
    adjustments: dict[str, "InboxAdjustment"] | None = None,
) -> list[dict]:
    """Return up to 5 prioritized emails for Telegram executive view.

    Hard filters applied before ranking:
    - Exclude newsletter/noise (low-value content, spam-equivalent)
    - Exclude read emails with no operational signal (no response/deadline/follow-up/opportunity)

    Ranking: priority (alta → media → baixa), then effective score descending
    (base score + memory adjustment), then original list order (stable sort
    preserves client ordering — Gmail returns newest first).
    """
    adj_map = adjustments or {}

    def _is_eligible(email: EmailMessage) -> bool:
        clf = classifications[email.id]
        if clf.category in ("newsletter", "noise"):
            return False
        has_action = (
            clf.requires_response
            or clf.has_deadline
            or clf.is_follow_up
            or clf.is_opportunity
        )
        has_financial_transaction = "FINANCIAL_TRANSACTION" in clf.audit_tags
        if email.is_read and not has_action and not has_financial_transaction:
            return False
        return True

    def _effective_score(email: EmailMessage) -> float:
        a = adj_map.get(email.id)
        if a is not None:
            return a.final
        return float(classifications[email.id].score)

    eligible = [e for e in emails if _is_eligible(e)]
    ranked = sorted(
        eligible,
        key=lambda e: (
            _PRIORITY_ORDER.get(classifications[e.id].priority, 2),
            -_effective_score(e),
        ),
    )

    result: list[dict] = []
    for email in ranked[:5]:
        clf = classifications[email.id]
        result.append({
            "id": email.id,
            "priority": clf.priority,
            "subject": email.subject,
            "sender": email.sender,
            "short_reason": build_short_reason(clf.audit_tags),
            "audit_tags": clf.audit_tags,
        })
    return result


def _log_email_classifications(
    emails: list[EmailMessage],
    classifications: dict[str, EmailClassification],
) -> None:
    """Log email classification events to memory. Fail-safe — never raises.

    The reference_id is normalized via `to_callback_ref` so the same value can
    be reused inside Telegram callback_data without exceeding the 64-byte limit.
    """
    try:
        from app.db.session import SessionLocal
        from app.modules.memory.service import MemoryService
        from app.modules.memory.utils import to_callback_ref

        db = SessionLocal()
        try:
            svc = MemoryService(db)
            for email in emails:
                clf = classifications.get(email.id)
                if not clf:
                    continue
                ref = to_callback_ref(email.id)
                if not ref:
                    continue
                svc.log_event(
                    event_type="email_classified",
                    source="email",
                    reference_id=ref,
                    payload={
                        "email_id": email.id,
                        "category": clf.category,
                        "priority": clf.priority,
                        "tags": clf.audit_tags,
                        "reason": clf.reason_codes,
                    },
                    score=float(clf.score),
                )
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Memory: falha ao logar classificacoes de email: %s", exc)


def _build_default_client() -> BaseEmailClient:
    provider = settings.email_provider.lower()
    if provider == "gmail":
        return GmailClient()
    if provider == "outlook":
        from app.integrations.outlook_client import OutlookClient

        return OutlookClient()
    raise NotImplementedError(f"Email provider nao suportado: {provider}")


def _classify_all(emails: list[EmailMessage]) -> dict[str, EmailClassification]:
    """Classify each email and mutate email.priority in place.

    InboxService is the authoritative source of classification.
    Any priority set by the client is overwritten here.
    Per-email errors are caught and logged — a single failure never aborts the summary.
    """
    result: dict[str, EmailClassification] = {}
    for email in emails:
        try:
            clf = classify_email(email)
            email.priority = clf.priority  # service is the source of truth
            result[email.id] = clf
        except Exception as exc:
            logger.warning("Falha ao classificar email %s: %s", email.id, exc)
            email.priority = "baixa"
            result[email.id] = _FALLBACK_CLASSIFICATION
    return result


class InboxService:
    def __init__(self, client: BaseEmailClient | None = None) -> None:
        self.client = client if client is not None else _build_default_client()

    def get_recent_emails(self, max_results: int = 10) -> list[dict]:
        """Return raw email list as dicts."""
        try:
            emails = self.client.list_recent_emails(max_results)
        except Exception as exc:
            logger.error("Falha ao buscar emails: %s", exc, exc_info=True)
            return []
        log_action(logger, "get_recent_emails", total=len(emails))
        return [email_to_dict(e) for e in emails]

    def summarize_emails(self) -> dict:
        """Classify and summarize inbox with priority breakdown and operational flags."""
        try:
            emails = self.client.list_recent_emails(max_results=20)
        except Exception as exc:
            logger.error("Falha ao buscar emails: %s", exc, exc_info=True)
            return {
                "total": 0,
                "high_priority": 0,
                "medium_priority": 0,
                "low_priority": 0,
                "unread": 0,
                "newsletter_count": 0,
                "items": [],
                "action_items": [],
                "top5": [],
                "summary": "Inbox temporariamente indisponivel.",
            }

        classifications = _classify_all(emails)
        _log_email_classifications(emails, classifications)

        # Adaptive scoring v1 (Etapa 3B): apply feedback-derived adjustments
        # AFTER classification, BEFORE ranking. Fail-safe — neutral on any error.
        adjustments = _compute_email_adjustments(emails, classifications)

        def _final_score(email: EmailMessage) -> float:
            a = adjustments.get(email.id)
            if a is not None:
                return a.final
            return float(classifications[email.id].score)

        high = [e for e in emails if classifications[e.id].priority == "alta"]
        medium = [e for e in emails if classifications[e.id].priority == "media"]
        low = [e for e in emails if classifications[e.id].priority == "baixa"]
        unread = [e for e in emails if not e.is_read]
        newsletter_count = sum(
            1 for e in emails if classifications[e.id].category == "newsletter"
        )

        # action_items: emails requiring direct action, ordered by effective score
        # descending (base score + memory adjustment). Hard exclusions unchanged:
        # newsletter/noise and PROMOTIONAL_NOISE.
        action_emails = sorted(
            [
                e for e in emails
                if classifications[e.id].category not in ("newsletter", "noise")
                and "PROMOTIONAL_NOISE" not in classifications[e.id].audit_tags
                and (
                    classifications[e.id].requires_response
                    or classifications[e.id].has_deadline
                    or classifications[e.id].is_follow_up
                    or classifications[e.id].is_opportunity
                )
            ],
            key=lambda e: -_final_score(e),
        )

        summary = _build_summary(emails, classifications, unread)

        result = {
            "total": len(emails),
            "high_priority": len(high),
            "medium_priority": len(medium),
            "low_priority": len(low),
            "unread": len(unread),
            "newsletter_count": newsletter_count,
            "items": [email_to_dict(e) for e in emails],
            "action_items": [email_to_dict(e) for e in action_emails],
            "top5": _build_top5(emails, classifications, adjustments),
            "summary": summary,
        }
        log_action(
            logger,
            "summarize_emails",
            total=result["total"],
            high_priority=result["high_priority"],
            unread=result["unread"],
        )
        return result

    # Backward compatibility alias
    def get_summary(self) -> dict:
        return self.summarize_emails()


def _build_summary(
    emails: list[EmailMessage],
    classifications: dict[str, EmailClassification],
    unread: list[EmailMessage],
) -> str:
    n_need_action = sum(
        1 for e in emails
        if classifications[e.id].requires_response or classifications[e.id].has_deadline
    )
    # follow-ups not already counted in need_action (avoid double counting)
    n_follow_up = sum(
        1 for e in emails
        if classifications[e.id].is_follow_up
        and not (classifications[e.id].requires_response or classifications[e.id].has_deadline)
    )
    n_newsletter = sum(1 for e in emails if classifications[e.id].category == "newsletter")
    n_noise = sum(1 for e in emails if classifications[e.id].category == "noise")

    parts = [f"{len(emails)} email(s)"]
    if n_need_action:
        parts.append(f"{n_need_action} exige(m) ação")
    if n_follow_up:
        parts.append(f"{n_follow_up} follow-up(s)")
    if n_newsletter:
        parts.append(f"{n_newsletter} newsletter(s)")
    if n_noise:
        parts.append(f"{n_noise} ruído(s)")
    if unread:
        parts.append(f"{len(unread)} não lido(s)")

    return " — ".join(parts) + "."
