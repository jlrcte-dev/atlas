"""Central email classifier — v2 with contextual score.

classify_email(email) -> EmailClassification

Decision order (mandatory):
  1. Determine category (newsletter/noise short-circuit is absolute)
  2. If newsletter or noise: score=0, priority=baixa, flags=False — return immediately
  3. For action/update: compute v1 flags, then derive score from flags + sender heuristic
  4. Derive priority from score via calibrated thresholds

No external dependencies. No LLM. Purely deterministic.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.integrations.email_models import EmailMessage

logger = logging.getLogger(__name__)

# ── Score model — single source of calibration ────────────────────────────────

SCORE_WEIGHTS: dict[str, int] = {
    "has_deadline": 4,        # deadline or urgency signal
    "requires_response": 4,   # explicit response expected
    "is_opportunity": 2,      # commercial/partnership signal
    "is_follow_up": 2,        # follow-up or reminder
    "human_sender": 2,        # named human contact (e.g. "Name <email>")
    "bulk_sender": -3,        # known bulk-mail sender (no-reply, mailer, etc.)
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
        )

    # Step 3: v1 flags (reused as score inputs — no redundant text processing)
    requires_response = _has_signal(text, _RESPONSE_SIGNALS, "requires_response", reason_codes)
    has_deadline = _has_signal(text, _DEADLINE_SIGNALS, "has_deadline", reason_codes)
    is_follow_up = _has_signal(text, _FOLLOW_UP_SIGNALS, "is_follow_up", reason_codes)
    is_opportunity = _has_signal(text, _OPPORTUNITY_SIGNALS, "is_opportunity", reason_codes)

    # Step 3: contextual score from v1 flags + sender heuristic
    score, score_reasons = _score_email(
        requires_response=requires_response,
        has_deadline=has_deadline,
        is_follow_up=is_follow_up,
        is_opportunity=is_opportunity,
        sender=email.sender,
    )

    # Step 4: priority from score (thresholds centralised above)
    priority = _derive_priority_from_score(score)

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
    )


# ── Private helpers ────────────────────────────────────────────────────────────


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
) -> tuple[int, list[str]]:
    """Compute contextual score from v1 flags and sender heuristic.

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
