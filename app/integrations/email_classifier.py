"""Central email classifier — v4 with PIX signals and learned-sender support.

classify_email(email) -> EmailClassification

Decision order (mandatory):
  1. Determine category (newsletter/noise short-circuit is absolute)
  2. If newsletter or noise: score=0, priority=baixa, flags=False, audit_tags=[NEWSLETTER_PENALIZED]
  3. For action/update: compute v1 flags + financial signal + learned-sender check, then derive score
  4. Derive priority from score via calibrated thresholds
  5. Build audit_tags from all signals for auditability

build_short_reason(audit_tags) -> str  (used by InboxService for Telegram output)

Learned senders: app/data/user_learning.json — loaded once per process via lru_cache.
Changes to the file require a process restart to take effect.

No external dependencies. No LLM. Purely deterministic.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.integrations.email_models import EmailMessage

logger = logging.getLogger(__name__)

_USER_LEARNING_PATH = Path(__file__).parent.parent / "data" / "user_learning.json"

# ── Score model — single source of calibration ────────────────────────────────

SCORE_WEIGHTS: dict[str, int] = {
    "has_deadline": 4,        # deadline or urgency signal
    "requires_response": 4,   # explicit response expected
    "is_opportunity": 2,      # commercial/partnership signal
    "is_follow_up": 2,        # follow-up or reminder
    "human_sender": 2,        # named human contact (e.g. "Name <email>")
    "bulk_sender": -3,        # known bulk-mail sender (no-reply, mailer, etc.)
    "learned_sender": 2,      # sender explicitly listed in user_learning.json
}

SCORE_THRESHOLD_HIGH: int = 4    # score >= 4 → "alta"
SCORE_THRESHOLD_MEDIUM: int = 0  # score >= 0 → "media"; score < 0 → "baixa"
# Newsletter/noise always bypass thresholds via short-circuit (score=0, priority=baixa)

# ── Signal sets ────────────────────────────────────────────────────────────────

_NEWSLETTER_SIGNALS = frozenset({
    "unsubscribe",
    "view in browser",
    "newsletter",
    "descadastrar",
    "cancelar inscrição",
    "cancelar inscricao",
    "boletim",
    "edição semanal",
    "edicao semanal",
    "edição mensal",
    "edicao mensal",
    "informativo semanal",
    "informativo mensal",
})

_NOISE_SIGNALS = frozenset({
    "oferta especial",
    "desconto imperdível",
    "desconto imperdivel",
    "cupom",
    "black friday",
    "cyber monday",
    "curtiu sua foto",
    "comentou sua publicação",
    "comentou sua publicacao",
    "nova mensagem no facebook",
    "nova mensagem no instagram",
})

_ACTION_VERBS = frozenset({
    # Imperative forms — direct requests
    "responda",
    "confirme",
    "envie",
    "aprove",
    "revise",
    "agende",
    "assine",
    "autorize",
    "preencha",
    # Infinitive forms — "precisa confirmar", "deve revisar"
    "responder",
    "confirmar",
    "aprovar",
    "revisar",
    "agendar",
    "assinar",
    "autorizar",
    "preencher",
    # Explicit patterns
    "action required",
    "ação necessária",
    "acao necessaria",
    "precisa ser aprovado",
    "precisa ser assinado",
})

_UPDATE_SIGNALS = frozenset({
    "atualização",
    "atualizacao",
    "status de",
    "status do",
    "status da",
    "retorno sobre",
    "relatório",
    "relatorio",
    "informando que",
    "comunicando que",
    "segue em anexo",
    "conforme solicitado",
    "comprovante",
})

_DEADLINE_SIGNALS = frozenset({
    "prazo",
    "urgente",
    "hoje",
    "amanhã",
    "amanha",
    "vencimento",
    "deadline",
    "data limite",
    "vence",
    "expira",
    "até amanhã",
    "ate amanha",
    "até hoje",
    "ate hoje",
    "até o dia",
    "ate o dia",
})

_FOLLOW_UP_SIGNALS = frozenset({
    "follow-up",
    "follow up",
    "followup",
    "lembrando",
    "lembrete",
    "conforme conversamos",
    "reforçando",
    "reforcando",
    "reminder",
    "acompanhamento",
    "retomando",
})

_OPPORTUNITY_SIGNALS = frozenset({
    "proposta",
    "parceria",
    "oportunidade",
    "convite",
    "orçamento",
    "orcamento",
    "reunião comercial",
    "reuniao comercial",
    "apresentação comercial",
    "apresentacao comercial",
})

_RESPONSE_SIGNALS = frozenset({
    "?",
    "aguardo",
    "aguardamos",
    "por favor",
    "por gentileza",
    "poderia",
    "pode me",
    "você pode",
    "voce pode",
    "preciso saber",
    "gostaria de saber",
})

# Bulk-sender substrings — penalise automated low-value senders
_BULK_SENDER_SIGNALS = frozenset({
    "no-reply",
    "noreply",
    "donotreply",
    "do-not-reply",
    "mailer",
    "notifications",
    "bounce",
})

# Financial/payment lexicon — adds FINANCIAL_TOPIC audit tag (no score impact)
_FINANCIAL_SIGNALS = frozenset({
    "pagamento",
    "fatura",
    "boleto",
    "nota fiscal",
    "cobrança",
    "cobranca",
    "débito",
    "debito",
    "transferência",
    "transferencia",
    "honorários",
    "honorarios",
    "contrato",
    "vencimento da fatura",
    "pagamento pendente",
    # PIX-specific signals
    "pix enviado",
    "pix recebido",
    "comprovante pix",
    "transferência pix",
    "transferencia pix",
    "pagamento pix",
})

# ── Result type ────────────────────────────────────────────────────────────────


@dataclass
class EmailClassification:
    category: str        # action | update | newsletter | noise
    priority: str        # alta | media | baixa
    requires_response: bool
    has_deadline: bool
    is_follow_up: bool
    is_opportunity: bool
    reason_codes: list[str] = field(default_factory=list)
    score: int = 0
    score_reasons: list[str] = field(default_factory=list)
    audit_tags: list[str] = field(default_factory=list)
    # Auditable tags: HAS_DEADLINE | ACTION_REQUIRED | FINANCIAL_TOPIC | FOLLOW_UP_PENDING |
    # OPPORTUNITY | IMPORTANT_SENDER | BULK_SENDER_PENALIZED | NEWSLETTER_PENALIZED


# ── Public helpers ─────────────────────────────────────────────────────────────

# Priority order for short_reason: first matching tag wins
_TAG_TO_REASON: tuple[tuple[str, str], ...] = (
    ("HAS_DEADLINE", "Prazo ou data identificada"),
    ("ACTION_REQUIRED", "Requer resposta/ação"),
    ("FINANCIAL_TOPIC", "Assunto financeiro/pagamento"),
    ("FOLLOW_UP_PENDING", "Follow-up pendente"),
    ("IMPORTANT_SENDER_LEARNED", "Remetente prioritário"),
    ("IMPORTANT_SENDER", "Remetente prioritário"),
    ("OPPORTUNITY", "Proposta/oportunidade"),
)


def build_short_reason(audit_tags: list[str]) -> str:
    """Map audit_tags to a single short human-readable reason for Telegram output."""
    for tag, reason in _TAG_TO_REASON:
        if tag in audit_tags:
            return reason
    return "Email relevante"


# ── Public API ─────────────────────────────────────────────────────────────────


def classify_email(email: EmailMessage) -> EmailClassification:
    """Classify an email deterministically.

    Uses sender + subject + snippet. Does not modify the email object.
    """
    text = f"{email.sender} {email.subject} {email.snippet}".lower()
    reason_codes: list[str] = []

    category = _classify_category(text, reason_codes)

    # Step 2: newsletter/noise — absolute short-circuit, no score computation
    if category in ("newsletter", "noise"):
        return EmailClassification(
            category=category,
            priority="baixa",
            requires_response=False,
            has_deadline=False,
            is_follow_up=False,
            is_opportunity=False,
            reason_codes=reason_codes,
            score=0,
            score_reasons=[],
            audit_tags=["NEWSLETTER_PENALIZED"],
        )

    # Step 3: v1 flags (reused as score inputs — no redundant text processing)
    requires_response = _has_signal(text, _RESPONSE_SIGNALS, "requires_response", reason_codes)
    has_deadline = _has_signal(text, _DEADLINE_SIGNALS, "has_deadline", reason_codes)
    is_follow_up = _has_signal(text, _FOLLOW_UP_SIGNALS, "is_follow_up", reason_codes)
    is_opportunity = _has_signal(text, _OPPORTUNITY_SIGNALS, "is_opportunity", reason_codes)
    is_financial = any(sig in text for sig in _FINANCIAL_SIGNALS)
    is_learned = _is_learned_sender(email.sender)

    # Step 3: contextual score from v1 flags + sender heuristic + learned sender
    score, score_reasons = _score_email(
        requires_response=requires_response,
        has_deadline=has_deadline,
        is_follow_up=is_follow_up,
        is_opportunity=is_opportunity,
        sender=email.sender,
        is_learned=is_learned,
    )

    # Step 4: priority from score (thresholds centralised above)
    priority = _derive_priority_from_score(score)

    # Step 5: build auditable tags from all computed signals
    audit_tags = _build_audit_tags(
        requires_response=requires_response,
        has_deadline=has_deadline,
        is_follow_up=is_follow_up,
        is_opportunity=is_opportunity,
        is_financial=is_financial,
        score_reasons=score_reasons,
    )

    return EmailClassification(
        category=category,
        priority=priority,
        requires_response=requires_response,
        has_deadline=has_deadline,
        is_follow_up=is_follow_up,
        is_opportunity=is_opportunity,
        reason_codes=reason_codes,
        score=score,
        score_reasons=score_reasons,
        audit_tags=audit_tags,
    )


# ── Private helpers ────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _load_learned_senders() -> frozenset[str]:
    """Load important sender addresses from user_learning.json.

    Cached for the process lifetime — file changes require restart.
    Returns empty frozenset on missing file or any parse error (never raises).
    """
    try:
        raw = json.loads(_USER_LEARNING_PATH.read_text(encoding="utf-8"))
        senders = frozenset(
            addr.strip().lower()
            for addr in raw.get("important_senders", [])
            if isinstance(addr, str) and addr.strip()
        )
        if senders:
            logger.debug("Loaded %d learned sender(s) from user_learning.json", len(senders))
        return senders
    except FileNotFoundError:
        return frozenset()
    except Exception as exc:
        logger.warning("Failed to load user_learning.json: %s", exc)
        return frozenset()


def _is_learned_sender(sender: str) -> bool:
    """Return True if sender's email address is in the user learning list.

    Extracts the address from 'Name <addr>' format for exact matching.
    Substring matching is intentionally avoided to prevent false positives.
    """
    learned = _load_learned_senders()
    if not learned:
        return False
    if "<" in sender and ">" in sender:
        addr = sender.split("<")[1].split(">")[0].strip().lower()
    else:
        addr = sender.strip().lower()
    return addr in learned


def _build_audit_tags(
    requires_response: bool,
    has_deadline: bool,
    is_follow_up: bool,
    is_opportunity: bool,
    is_financial: bool,
    score_reasons: list[str],
) -> list[str]:
    """Build ordered audit tags from computed signals. Used for Telegram short_reason."""
    tags: list[str] = []
    if has_deadline:
        tags.append("HAS_DEADLINE")
    if requires_response:
        tags.append("ACTION_REQUIRED")
    if is_financial:
        tags.append("FINANCIAL_TOPIC")
    if is_follow_up:
        tags.append("FOLLOW_UP_PENDING")
    if is_opportunity:
        tags.append("OPPORTUNITY")
    if "learned_sender" in score_reasons:
        tags.append("IMPORTANT_SENDER_LEARNED")
    if "human_sender" in score_reasons:
        tags.append("IMPORTANT_SENDER")
    if "bulk_sender" in score_reasons:
        tags.append("BULK_SENDER_PENALIZED")
    return tags


def _classify_category(text: str, reason_codes: list[str]) -> str:
    """Precedence: newsletter → noise → action → update (update is the safe default)."""
    if _has_signal(text, _NEWSLETTER_SIGNALS, "newsletter", reason_codes):
        return "newsletter"
    if _has_signal(text, _NOISE_SIGNALS, "noise", reason_codes):
        return "noise"
    if _has_signal(text, _ACTION_VERBS, "action", reason_codes):
        return "action"
    if _has_signal(text, _UPDATE_SIGNALS, "update", reason_codes):
        return "update"
    return "update"


def _score_email(
    requires_response: bool,
    has_deadline: bool,
    is_follow_up: bool,
    is_opportunity: bool,
    sender: str,
    is_learned: bool = False,
) -> tuple[int, list[str]]:
    """Compute contextual score from v1 flags, sender heuristic, and learned-sender check.

    Reuses already-computed flags — no redundant text scanning.
    """
    score = 0
    reasons: list[str] = []

    if has_deadline:
        score += SCORE_WEIGHTS["has_deadline"]
        reasons.append("has_deadline")
    if requires_response:
        score += SCORE_WEIGHTS["requires_response"]
        reasons.append("requires_response")
    if is_opportunity:
        score += SCORE_WEIGHTS["is_opportunity"]
        reasons.append("is_opportunity")
    if is_follow_up:
        score += SCORE_WEIGHTS["is_follow_up"]
        reasons.append("is_follow_up")

    sender_pts, sender_reason = _sender_score(sender)
    if sender_pts != 0:
        score += sender_pts
        if sender_reason:
            reasons.append(sender_reason)

    if is_learned:
        score += SCORE_WEIGHTS["learned_sender"]
        reasons.append("learned_sender")

    return score, reasons


def _sender_score(sender: str) -> tuple[int, str | None]:
    """Return score contribution and reason label for the sender address.

    Bulk-mail signals penalise; named human contacts get a small boost.
    """
    s = sender.lower()
    if any(sig in s for sig in _BULK_SENDER_SIGNALS):
        return SCORE_WEIGHTS["bulk_sender"], "bulk_sender"
    # Named contact: "Full Name <addr@domain>" — angle bracket with a name prefix
    if "<" in sender and sender.split("<")[0].strip():
        return SCORE_WEIGHTS["human_sender"], "human_sender"
    return 0, None


def _derive_priority_from_score(score: int) -> str:
    if score >= SCORE_THRESHOLD_HIGH:
        return "alta"
    if score >= SCORE_THRESHOLD_MEDIUM:
        return "media"
    return "baixa"


def _has_signal(
    text: str, signals: frozenset[str], code: str, reason_codes: list[str]
) -> bool:
    for signal in signals:
        if signal in text:
            reason_codes.append(code)
            return True
    return False
