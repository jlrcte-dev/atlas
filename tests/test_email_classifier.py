"""Unit tests for the central email classifier and InboxService classification flow.

Covers: category detection, flags, priority derivation, newsletter/noise
short-circuit, resilience, and service-level source-of-truth behaviour.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.integrations.email_classifier import classify_email
from app.integrations.email_models import EmailMessage
from app.modules.inbox.service import InboxService
from app.integrations.email_models import EmailMessage


def _make(
    subject: str = "",
    snippet: str = "",
    sender: str = "remetente@example.com",
    is_read: bool = True,
    id: str = "test-id",
    priority: str = "baixa",
) -> EmailMessage:
    return EmailMessage(
        id=id,
        sender=sender,
        subject=subject,
        snippet=snippet,
        priority=priority,
        timestamp="",
        is_read=is_read,
    )


# ── Category: newsletter ───────────────────────────────────────────────────────


def test_newsletter_via_unsubscribe():
    email = _make(snippet="Click here to unsubscribe from this list.")
    clf = classify_email(email)
    assert clf.category == "newsletter"
    assert clf.priority == "baixa"


def test_newsletter_via_signal_in_subject():
    email = _make(subject="Newsletter semanal — edição semanal de abril")
    clf = classify_email(email)
    assert clf.category == "newsletter"
    assert clf.priority == "baixa"


def test_newsletter_short_circuits_all_flags():
    """Newsletter with deadline/action language must still be baixa with no flags."""
    email = _make(
        subject="Newsletter urgente — responda agora! prazo hoje",
        snippet="unsubscribe | view in browser",
    )
    clf = classify_email(email)
    assert clf.category == "newsletter"
    assert clf.priority == "baixa"
    assert clf.requires_response is False
    assert clf.has_deadline is False
    assert clf.is_follow_up is False
    assert clf.is_opportunity is False


# ── Category: noise ────────────────────────────────────────────────────────────


def test_noise_promotional():
    email = _make(subject="Oferta especial só para você — 60% OFF")
    clf = classify_email(email)
    assert clf.category == "noise"
    assert clf.priority == "baixa"


def test_noise_social():
    email = _make(snippet="João curtiu sua foto.")
    clf = classify_email(email)
    assert clf.category == "noise"
    assert clf.priority == "baixa"


def test_noise_short_circuits_flags():
    """Noise email with urgent language must stay baixa with no flags."""
    email = _make(
        subject="Oferta especial — prazo hoje! aguardo sua resposta",
    )
    clf = classify_email(email)
    assert clf.category == "noise"
    assert clf.priority == "baixa"
    assert clf.requires_response is False
    assert clf.has_deadline is False


# ── Category: action ───────────────────────────────────────────────────────────


def test_action_via_imperative_verb():
    email = _make(subject="Documento para assinar — urgente")
    clf = classify_email(email)
    assert clf.category == "action"


def test_action_via_infinitive_verb():
    email = _make(snippet="Precisa ser aprovado até o final do dia.")
    clf = classify_email(email)
    assert clf.category == "action"


def test_action_via_explicit_pattern():
    email = _make(subject="Action required: approve the proposal")
    clf = classify_email(email)
    assert clf.category == "action"


def test_action_priority_is_alta():
    email = _make(subject="Por favor revise o contrato")
    clf = classify_email(email)
    assert clf.category == "action"
    assert clf.priority == "alta"


# ── Category: update ──────────────────────────────────────────────────────────


def test_update_via_status_signal():
    email = _make(subject="Atualização sobre o pedido #1234")
    clf = classify_email(email)
    assert clf.category == "update"


def test_update_via_report_signal():
    email = _make(snippet="Segue em anexo o relatório mensal de vendas.")
    clf = classify_email(email)
    assert clf.category == "update"


def test_update_priority_is_media():
    email = _make(subject="Retorno sobre reunião de ontem")
    clf = classify_email(email)
    assert clf.category == "update"
    assert clf.priority == "media"


# ── Flag: requires_response ────────────────────────────────────────────────────


def test_requires_response_via_question_mark():
    email = _make(subject="Você pode confirmar o horário?")
    clf = classify_email(email)
    assert clf.requires_response is True
    assert clf.priority == "alta"


def test_requires_response_via_aguardo():
    email = _make(snippet="Aguardo seu retorno sobre o assunto.")
    clf = classify_email(email)
    assert clf.requires_response is True


def test_requires_response_via_por_favor():
    email = _make(snippet="Por favor, confirme o recebimento.")
    clf = classify_email(email)
    assert clf.requires_response is True


# ── Flag: has_deadline ────────────────────────────────────────────────────────


def test_has_deadline_via_prazo():
    email = _make(subject="Proposta — prazo de entrega amanhã")
    clf = classify_email(email)
    assert clf.has_deadline is True
    assert clf.priority == "alta"


def test_has_deadline_via_vencimento():
    email = _make(snippet="O vencimento da fatura é hoje.")
    clf = classify_email(email)
    assert clf.has_deadline is True
    assert clf.priority == "alta"


def test_has_deadline_via_deadline():
    email = _make(subject="Projeto X — deadline: sexta-feira")
    clf = classify_email(email)
    assert clf.has_deadline is True


# ── Flag: is_follow_up ────────────────────────────────────────────────────────


def test_is_follow_up_via_signal():
    email = _make(subject="Follow-up: proposta enviada na semana passada")
    clf = classify_email(email)
    assert clf.is_follow_up is True


def test_is_follow_up_via_conforme_conversamos():
    email = _make(snippet="Conforme conversamos, segue o material solicitado.")
    clf = classify_email(email)
    assert clf.is_follow_up is True


def test_is_follow_up_via_lembrando():
    email = _make(subject="Lembrando sobre a reunião de amanhã")
    clf = classify_email(email)
    assert clf.is_follow_up is True


# ── Flag: is_opportunity ──────────────────────────────────────────────────────


def test_is_opportunity_via_proposta():
    email = _make(subject="Proposta de parceria — reunião comercial")
    clf = classify_email(email)
    assert clf.is_opportunity is True


def test_is_opportunity_via_orcamento():
    email = _make(snippet="Segue o orçamento conforme solicitado.")
    clf = classify_email(email)
    assert clf.is_opportunity is True


# ── Priority derivation ────────────────────────────────────────────────────────


def test_priority_alta_when_action_category():
    # v2: action verbs alone (no response/deadline flag, no named sender) → score=0 → media
    # Priority comes from score; action category does not add score by itself.
    email = _make(subject="Documento para assinar")
    clf = classify_email(email)
    assert clf.category == "action"
    assert clf.priority == "media"
    assert clf.score == 0


def test_priority_alta_when_requires_response():
    email = _make(subject="Retorno sobre o relatório — aguardo")
    clf = classify_email(email)
    assert clf.priority == "alta"


def test_priority_alta_when_has_deadline():
    email = _make(subject="Relatório mensal — prazo hoje")
    clf = classify_email(email)
    assert clf.priority == "alta"


def test_priority_media_for_update_without_flags():
    email = _make(subject="Atualização: sistema voltou ao normal")
    clf = classify_email(email)
    assert clf.priority == "media"
    assert clf.requires_response is False
    assert clf.has_deadline is False


def test_priority_baixa_for_newsletter():
    email = _make(subject="Nossa newsletter mensal — boletim de março")
    clf = classify_email(email)
    assert clf.priority == "baixa"


# ── Resilience ────────────────────────────────────────────────────────────────


def test_empty_fields_do_not_crash():
    email = _make(subject="", snippet="", sender="")
    clf = classify_email(email)
    assert clf.category in ("action", "update", "newsletter", "noise")
    assert clf.priority in ("alta", "media", "baixa")


def test_reason_codes_populated():
    email = _make(subject="Documento para assinar — prazo amanhã")
    clf = classify_email(email)
    assert len(clf.reason_codes) > 0


# ── Isolation: newsletter always wins over action/deadline ────────────────────


def test_newsletter_beats_action_language():
    """A newsletter that contains action verbs must NOT become action category."""
    email = _make(
        subject="Newsletter — confirme sua presença no evento",
        snippet="Para descadastrar clique aqui. unsubscribe",
    )
    clf = classify_email(email)
    assert clf.category == "newsletter"
    assert clf.priority == "baixa"
    assert clf.requires_response is False


def test_noise_beats_action_language():
    """A promo email that contains action verbs must NOT become action."""
    email = _make(
        subject="Oferta especial — aprove já seu desconto imperdível",
    )
    clf = classify_email(email)
    assert clf.category == "noise"
    assert clf.priority == "baixa"


# ── InboxService: source of truth ─────────────────────────────────────────────


def _make_client(emails: list[EmailMessage]) -> MagicMock:
    client = MagicMock()
    client.list_recent_emails.return_value = emails
    return client


def test_service_reclassifies_overriding_client_priority():
    """InboxService must overwrite any priority set by the client."""
    email = _make(
        subject="Por favor assine o contrato urgente",
        priority="media",  # wrong placeholder from client
    )
    svc = InboxService(client=_make_client([email]))
    result = svc.summarize_emails()

    assert result["high_priority"] == 1
    assert result["items"][0]["priority"] == "alta"
    assert len(result["action_items"]) == 1


def test_service_items_priority_matches_classification():
    """Priority in items[] must reflect the service classification, not client value."""
    newsletter = _make(
        subject="Nossa newsletter semanal — boletim de abril",
        snippet="unsubscribe",
        priority="alta",  # client set this wrongly
    )
    svc = InboxService(client=_make_client([newsletter]))
    result = svc.summarize_emails()

    assert result["items"][0]["priority"] == "baixa"
    assert result["action_items"] == []
    assert result["low_priority"] == 1


def test_service_resilient_when_one_classification_fails():
    """Classification failure for one email must not abort the whole summary."""
    good = _make(id="good", subject="Relatório mensal — atualização")
    bad = _make(id="bad", subject="")

    original = classify_email

    def classify_side_effect(email: EmailMessage):
        if email.id == "bad":
            raise RuntimeError("simulated failure")
        return original(email)

    svc = InboxService(client=_make_client([good, bad]))
    with patch("app.modules.inbox.service.classify_email", side_effect=classify_side_effect):
        result = svc.summarize_emails()

    assert result["total"] == 2
    assert isinstance(result["action_items"], list)
    assert isinstance(result["summary"], str)
    # failed email falls back to baixa
    priorities = {item["id"]: item["priority"] for item in result["items"]}
    assert priorities["bad"] == "baixa"


# ── Summary format ────────────────────────────────────────────────────────────


def test_summary_separates_newsletter_and_noise():
    """Newsletter and noise must appear as distinct counts in the summary."""
    newsletter = _make(id="n1", snippet="unsubscribe")
    noise = _make(id="n2", subject="Oferta especial — desconto imperdível")
    action = _make(id="a1", subject="Por favor revise o documento urgente")

    svc = InboxService(client=_make_client([newsletter, noise, action]))
    result = svc.summarize_emails()

    summary = result["summary"]
    assert "newsletter" in summary
    assert "ruído" in summary
    # newsletter and noise must NOT be merged into a single "newsletter/ruído" token
    assert "newsletter(s)/ruído" not in summary


def test_summary_basic_format():
    """Summary must start with total count and end with period."""
    email = _make(subject="Atualização do sistema")
    svc = InboxService(client=_make_client([email]))
    result = svc.summarize_emails()

    assert result["summary"].startswith("1 email(s)")
    assert result["summary"].endswith(".")


# ── v2: Score contextual ──────────────────────────────────────────────────────


def test_score_zero_for_newsletter():
    """Newsletter short-circuit must produce score=0."""
    email = _make(snippet="Para cancelar sua inscrição, clique em unsubscribe.")
    clf = classify_email(email)
    assert clf.category == "newsletter"
    assert clf.score == 0
    assert clf.score_reasons == []
    assert clf.priority == "baixa"


def test_score_zero_for_noise():
    """Noise short-circuit must produce score=0."""
    email = _make(subject="Oferta especial — desconto imperdível")
    clf = classify_email(email)
    assert clf.category == "noise"
    assert clf.score == 0
    assert clf.score_reasons == []
    assert clf.priority == "baixa"


def test_score_high_from_deadline():
    """has_deadline alone must produce score >= SCORE_THRESHOLD_HIGH → alta."""
    from app.integrations.email_classifier import SCORE_THRESHOLD_HIGH, SCORE_WEIGHTS

    email = _make(subject="Prazo de entrega vence hoje — confirmação necessária")
    clf = classify_email(email)
    assert clf.has_deadline is True
    assert clf.score >= SCORE_THRESHOLD_HIGH
    assert clf.priority == "alta"
    assert "has_deadline" in clf.score_reasons


def test_score_high_from_requires_response():
    """requires_response alone must produce score >= SCORE_THRESHOLD_HIGH → alta."""
    from app.integrations.email_classifier import SCORE_THRESHOLD_HIGH

    email = _make(subject="Aguardo seu retorno sobre a proposta")
    clf = classify_email(email)
    assert clf.requires_response is True
    assert clf.score >= SCORE_THRESHOLD_HIGH
    assert clf.priority == "alta"
    assert "requires_response" in clf.score_reasons


def test_score_medium_from_is_follow_up():
    """is_follow_up alone (no named sender) must produce media priority."""
    from app.integrations.email_classifier import SCORE_THRESHOLD_HIGH, SCORE_THRESHOLD_MEDIUM, SCORE_WEIGHTS

    email = _make(subject="Lembrando: aguardamos seu retorno sobre a reunião de ontem")
    # "lembrando" → is_follow_up; "aguardamos" → requires_response (score=4=alta)
    # Use acompanhamento which triggers only follow-up
    email = _make(subject="Acompanhamento sobre nossa conversa de ontem")
    clf = classify_email(email)
    assert clf.is_follow_up is True
    assert clf.score >= SCORE_THRESHOLD_MEDIUM
    assert clf.score < SCORE_THRESHOLD_HIGH
    assert clf.priority == "media"
    assert "is_follow_up" in clf.score_reasons


def test_score_medium_from_is_opportunity():
    """is_opportunity alone must contribute score and produce media priority."""
    from app.integrations.email_classifier import SCORE_THRESHOLD_HIGH, SCORE_THRESHOLD_MEDIUM

    email = _make(subject="Proposta de parceria para nossos negócios")
    clf = classify_email(email)
    assert clf.is_opportunity is True
    assert clf.score >= SCORE_THRESHOLD_MEDIUM
    assert clf.score < SCORE_THRESHOLD_HIGH
    assert clf.priority == "media"
    assert "is_opportunity" in clf.score_reasons


def test_score_bulk_sender_penalty():
    """Bulk-sender signal must reduce score."""
    email_bulk = _make(
        subject="Retorno sobre o projeto",
        sender="no-reply@sistema.com",
    )
    email_normal = _make(
        subject="Retorno sobre o projeto",
        sender="sistema@empresa.com",
    )
    clf_bulk = classify_email(email_bulk)
    clf_normal = classify_email(email_normal)

    assert clf_bulk.score < clf_normal.score
    assert "bulk_sender" in clf_bulk.score_reasons


def test_score_bulk_sender_lowers_priority():
    """Bulk sender should penalise score — no flags + bulk → baixa."""
    email = _make(
        subject="Atualização do sistema",
        sender="noreply@empresa.com",
    )
    clf = classify_email(email)
    assert "bulk_sender" in clf.score_reasons
    assert clf.score < 0
    assert clf.priority == "baixa"


def test_score_human_sender_bonus():
    """Named human sender must boost score."""
    email_named = _make(
        subject="Atualização sobre o projeto",
        sender="Ana Lima <ana@empresa.com>",
    )
    email_bare = _make(
        subject="Atualização sobre o projeto",
        sender="sistema@empresa.com",
    )
    clf_named = classify_email(email_named)
    clf_bare = classify_email(email_bare)

    assert clf_named.score > clf_bare.score
    assert "human_sender" in clf_named.score_reasons


def test_score_human_sender_raises_priority_to_media():
    """Named human sender alone (no flags) must yield at least media."""
    email = _make(
        subject="Olá, tudo bem?",
        sender="João Silva <joao@empresa.com>",
    )
    clf = classify_email(email)
    assert "human_sender" in clf.score_reasons
    assert clf.priority in ("media", "alta")


def test_score_combined_deadline_and_response():
    """Combining has_deadline and requires_response must produce very high score → alta."""
    from app.integrations.email_classifier import SCORE_WEIGHTS

    email = _make(subject="Urgente — prazo hoje. Aguardo sua confirmação?")
    clf = classify_email(email)

    assert clf.has_deadline is True
    assert clf.requires_response is True
    assert clf.score >= SCORE_WEIGHTS["has_deadline"] + SCORE_WEIGHTS["requires_response"]
    assert clf.priority == "alta"


def test_score_newsletter_with_deadline_language_stays_baixa():
    """Newsletter with deadline language must remain baixa — short-circuit is absolute."""
    email = _make(
        subject="Newsletter — urgente, prazo hoje! Aguardo",
        snippet="Para descadastrar clique em unsubscribe.",
    )
    clf = classify_email(email)
    assert clf.category == "newsletter"
    assert clf.priority == "baixa"
    assert clf.score == 0


def test_action_items_ordered_by_score():
    """action_items must be ordered by score descending (highest first)."""
    # Low score: is_follow_up only (score=2)
    low = _make(id="low", subject="Follow-up: acompanhamento sobre nosso contato")
    # High score: has_deadline + requires_response (score >= 8)
    high = _make(id="high", subject="Prazo hoje — aguardo sua resposta urgente?")
    # Medium score: is_opportunity (score=2) — same as low but opportunity
    medium = _make(id="med", subject="Proposta comercial — reunião comercial amanhã")

    svc = InboxService(client=_make_client([low, high, medium]))
    result = svc.summarize_emails()

    ids = [item["id"] for item in result["action_items"]]
    # high must come before the others
    assert ids[0] == "high"
