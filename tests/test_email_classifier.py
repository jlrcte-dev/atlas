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


# ── v3: Audit tags ────────────────────────────────────────────────────────────


def test_audit_tags_newsletter_penalized():
    """Newsletter and noise must produce exactly [NEWSLETTER_PENALIZED]."""
    nl = _make(snippet="unsubscribe from this list")
    clf = classify_email(nl)
    assert clf.audit_tags == ["NEWSLETTER_PENALIZED"]


def test_audit_tags_noise_penalized():
    noise = _make(subject="Oferta especial — desconto imperdível hoje")
    clf = classify_email(noise)
    assert clf.audit_tags == ["NEWSLETTER_PENALIZED"]


def test_audit_tags_has_deadline():
    email = _make(subject="Relatório — prazo amanhã")
    clf = classify_email(email)
    assert "HAS_DEADLINE" in clf.audit_tags


def test_audit_tags_action_required():
    email = _make(subject="Aguardo sua resposta sobre o contrato")
    clf = classify_email(email)
    assert "ACTION_REQUIRED" in clf.audit_tags


def test_audit_tags_financial_topic():
    email = _make(subject="Pagamento de fatura — boleto em anexo")
    clf = classify_email(email)
    assert "FINANCIAL_TOPIC" in clf.audit_tags


def test_audit_tags_follow_up_pending():
    email = _make(subject="Acompanhamento sobre nossa conversa de ontem")
    clf = classify_email(email)
    assert "FOLLOW_UP_PENDING" in clf.audit_tags


def test_audit_tags_important_sender():
    email = _make(
        subject="Atualização do projeto",
        sender="Ana Lima <ana@empresa.com>",
    )
    clf = classify_email(email)
    assert "IMPORTANT_SENDER" in clf.audit_tags


def test_audit_tags_bulk_sender_penalized():
    email = _make(
        subject="Atualização do sistema",
        sender="noreply@plataforma.com",
    )
    clf = classify_email(email)
    assert "BULK_SENDER_PENALIZED" in clf.audit_tags


def test_audit_tags_empty_for_plain_update():
    """Plain update with no signals and anonymous sender must have no audit tags."""
    email = _make(subject="Retorno sobre reunião de ontem")
    clf = classify_email(email)
    assert clf.audit_tags == []


# ── v3: build_short_reason ────────────────────────────────────────────────────


def test_build_short_reason_deadline_takes_precedence():
    """HAS_DEADLINE must win over other tags in short_reason."""
    from app.integrations.email_classifier import build_short_reason

    tags = ["HAS_DEADLINE", "ACTION_REQUIRED", "FOLLOW_UP_PENDING"]
    assert build_short_reason(tags) == "Prazo ou data identificada"


def test_build_short_reason_action_required():
    from app.integrations.email_classifier import build_short_reason

    assert build_short_reason(["ACTION_REQUIRED"]) == "Requer resposta/ação"


def test_build_short_reason_financial():
    from app.integrations.email_classifier import build_short_reason

    assert build_short_reason(["FINANCIAL_TOPIC"]) == "Assunto financeiro/pagamento"


def test_build_short_reason_fallback():
    from app.integrations.email_classifier import build_short_reason

    assert build_short_reason([]) == "Email relevante"
    assert build_short_reason(["NEWSLETTER_PENALIZED"]) == "Email relevante"


# ── v3: Financial signal detection ───────────────────────────────────────────


def test_financial_signal_via_subject():
    email = _make(subject="Boleto de pagamento — vence hoje")
    clf = classify_email(email)
    assert "FINANCIAL_TOPIC" in clf.audit_tags


def test_financial_signal_via_snippet():
    email = _make(snippet="Segue em anexo a nota fiscal para conferência.")
    clf = classify_email(email)
    assert "FINANCIAL_TOPIC" in clf.audit_tags


def test_financial_signal_does_not_change_score():
    """Financial detection is audit-only — must not alter the score."""
    email_financial = _make(subject="Pagamento da fatura mensal")
    email_plain = _make(subject="Atualização do sistema")
    clf_f = classify_email(email_financial)
    clf_p = classify_email(email_plain)
    assert clf_f.score == clf_p.score


def test_financial_newsletter_stays_baixa():
    """Financial signals inside a newsletter must not escape the short-circuit."""
    email = _make(
        subject="Newsletter — fatura e pagamento de assinaturas",
        snippet="unsubscribe",
    )
    clf = classify_email(email)
    assert clf.category == "newsletter"
    assert clf.priority == "baixa"
    assert clf.audit_tags == ["NEWSLETTER_PENALIZED"]


# ── v3: Service top5 ──────────────────────────────────────────────────────────


def test_top5_excludes_newsletter():
    nl = _make(id="nl", snippet="Para descadastrar clique em unsubscribe.", is_read=False)
    action = _make(id="act", subject="Prazo hoje — aguardo confirmação?")
    svc = InboxService(client=_make_client([nl, action]))
    result = svc.summarize_emails()
    top5_ids = [item["id"] for item in result["top5"]]
    assert "nl" not in top5_ids
    assert "act" in top5_ids


def test_top5_excludes_noise():
    noise = _make(id="nz", subject="Oferta especial — cupom imperdível!", is_read=False)
    action = _make(id="act", subject="Aguardo sua resposta urgente.")
    svc = InboxService(client=_make_client([noise, action]))
    result = svc.summarize_emails()
    top5_ids = [item["id"] for item in result["top5"]]
    assert "nz" not in top5_ids
    assert "act" in top5_ids


def test_top5_excludes_read_without_action():
    """Read email with no operational flags must be excluded from top5."""
    read_plain = _make(id="r", subject="Atualização do sistema", is_read=True)
    unread_plain = _make(id="u", subject="Relatório mensal", is_read=False)
    svc = InboxService(client=_make_client([read_plain, unread_plain]))
    result = svc.summarize_emails()
    top5_ids = [item["id"] for item in result["top5"]]
    assert "r" not in top5_ids
    assert "u" in top5_ids


def test_top5_includes_read_with_deadline():
    """Read email WITH deadline flag must NOT be excluded from top5."""
    read_with_deadline = _make(
        id="rwdl",
        subject="Prazo de entrega — vencimento amanhã",
        is_read=True,
    )
    svc = InboxService(client=_make_client([read_with_deadline]))
    result = svc.summarize_emails()
    top5_ids = [item["id"] for item in result["top5"]]
    assert "rwdl" in top5_ids


def test_top5_ordering_alta_before_media():
    """Alta-priority email must appear before media-priority in top5."""
    media = _make(id="med", subject="Acompanhamento sobre nossa conversa de ontem")
    alta = _make(id="alta", subject="Prazo hoje — aguardo confirmação urgente?")
    svc = InboxService(client=_make_client([media, alta]))
    result = svc.summarize_emails()
    top5 = result["top5"]
    assert top5[0]["id"] == "alta"
    assert top5[0]["priority"] == "alta"


def test_top5_has_required_fields():
    """Each top5 item must expose priority, subject, sender, short_reason, audit_tags."""
    email = _make(subject="Prazo hoje — aguardo confirmação?")
    svc = InboxService(client=_make_client([email]))
    result = svc.summarize_emails()
    assert len(result["top5"]) == 1
    item = result["top5"][0]
    for field_name in ("id", "priority", "subject", "sender", "short_reason", "audit_tags"):
        assert field_name in item, f"top5 item missing field: {field_name}"
    assert isinstance(item["short_reason"], str)
    assert len(item["short_reason"]) > 0


def test_top5_short_reason_maps_correctly():
    """Email with deadline must produce 'Prazo ou data identificada' as short_reason."""
    email = _make(subject="Contrato — prazo amanhã para assinatura")
    svc = InboxService(client=_make_client([email]))
    result = svc.summarize_emails()
    assert result["top5"][0]["short_reason"] == "Prazo ou data identificada"


def test_result_has_newsletter_count():
    """summarize_emails() must include newsletter_count in result."""
    nl = _make(id="nl", snippet="unsubscribe from this list")
    act = _make(id="act", subject="Por favor revise este documento urgente")
    svc = InboxService(client=_make_client([nl, act]))
    result = svc.summarize_emails()
    assert "newsletter_count" in result
    assert result["newsletter_count"] == 1


def test_result_has_top5():
    """summarize_emails() must include top5 in result."""
    email = _make(subject="Atualização do sistema", is_read=False)
    svc = InboxService(client=_make_client([email]))
    result = svc.summarize_emails()
    assert "top5" in result
    assert isinstance(result["top5"], list)


# ── v4: PIX signals ────────────────────────────────────────────────────────────


def test_pix_enviado_detected():
    email = _make(subject="Pix enviado com sucesso — R$ 150,00")
    clf = classify_email(email)
    assert "FINANCIAL_TOPIC" in clf.audit_tags


def test_pix_recebido_detected():
    email = _make(snippet="Você recebeu um pix recebido de João Lima.")
    clf = classify_email(email)
    assert "FINANCIAL_TOPIC" in clf.audit_tags


def test_comprovante_pix_detected():
    email = _make(subject="Comprovante pix — transferência realizada")
    clf = classify_email(email)
    assert "FINANCIAL_TOPIC" in clf.audit_tags


def test_transferencia_pix_detected():
    email = _make(subject="Transferência pix agendada para amanhã")
    clf = classify_email(email)
    assert "FINANCIAL_TOPIC" in clf.audit_tags


def test_pagamento_pix_detected():
    email = _make(snippet="Segue o pagamento pix conforme solicitado.")
    clf = classify_email(email)
    assert "FINANCIAL_TOPIC" in clf.audit_tags


def test_pix_in_newsletter_stays_baixa():
    """PIX signal inside a newsletter must not escape the newsletter short-circuit."""
    email = _make(
        subject="Newsletter — comprovante pix e pagamento pix disponíveis",
        snippet="Para descadastrar clique em unsubscribe.",
    )
    clf = classify_email(email)
    assert clf.category == "newsletter"
    assert clf.priority == "baixa"
    assert clf.audit_tags == ["NEWSLETTER_PENALIZED"]
    assert "FINANCIAL_TOPIC" not in clf.audit_tags


def test_pix_does_not_change_score():
    """PIX detection is audit-only — must not alter the score."""
    with_pix = _make(subject="Pix enviado — R$ 200,00")
    without_pix = _make(subject="Atualização de sistema")
    clf_pix = classify_email(with_pix)
    clf_plain = classify_email(without_pix)
    assert clf_pix.score == clf_plain.score


# ── v4: Learned senders ───────────────────────────────────────────────────────


def test_learned_sender_adds_tag():
    """Sender in learning list must receive IMPORTANT_SENDER_LEARNED tag."""
    with patch(
        "app.integrations.email_classifier._load_learned_senders",
        return_value=frozenset({"vip@parceiro.com"}),
    ):
        email = _make(subject="Proposta de projeto", sender="vip@parceiro.com")
        clf = classify_email(email)
    assert "IMPORTANT_SENDER_LEARNED" in clf.audit_tags


def test_learned_sender_with_display_name():
    """Learned sender extracted from 'Name <addr>' format must match."""
    with patch(
        "app.integrations.email_classifier._load_learned_senders",
        return_value=frozenset({"vip@parceiro.com"}),
    ):
        email = _make(subject="Reunião amanhã", sender="Ana VIP <vip@parceiro.com>")
        clf = classify_email(email)
    assert "IMPORTANT_SENDER_LEARNED" in clf.audit_tags


def test_learned_sender_boosts_score():
    """Learned sender must increase score compared to same email without learned flag."""
    base_subject = "Atualização sobre o projeto"
    with patch(
        "app.integrations.email_classifier._load_learned_senders",
        return_value=frozenset({"vip@parceiro.com"}),
    ):
        clf_learned = classify_email(_make(subject=base_subject, sender="vip@parceiro.com"))
    clf_normal = classify_email(_make(subject=base_subject, sender="vip@parceiro.com"))
    assert clf_learned.score > clf_normal.score
    assert "learned_sender" in clf_learned.score_reasons


def test_learned_sender_raises_priority_to_media():
    """Learned anonymous sender alone must yield at least media priority."""
    with patch(
        "app.integrations.email_classifier._load_learned_senders",
        return_value=frozenset({"vip@parceiro.com"}),
    ):
        email = _make(subject="Olá, tudo certo?", sender="vip@parceiro.com")
        clf = classify_email(email)
    assert clf.priority in ("media", "alta")


def test_learned_sender_not_in_list_no_tag():
    """Sender NOT in learning list must not receive IMPORTANT_SENDER_LEARNED."""
    with patch(
        "app.integrations.email_classifier._load_learned_senders",
        return_value=frozenset({"outro@empresa.com"}),
    ):
        email = _make(subject="Atualização", sender="nao@listado.com")
        clf = classify_email(email)
    assert "IMPORTANT_SENDER_LEARNED" not in clf.audit_tags


def test_learned_sender_exact_match_no_false_positive():
    """Partial address overlap must NOT match ('naojoao@' vs 'joao@')."""
    with patch(
        "app.integrations.email_classifier._load_learned_senders",
        return_value=frozenset({"joao@empresa.com"}),
    ):
        email = _make(subject="Contato", sender="naojoao@empresa.com")
        clf = classify_email(email)
    assert "IMPORTANT_SENDER_LEARNED" not in clf.audit_tags


def test_learned_sender_newsletter_stays_baixa():
    """Learned sender that sends a newsletter must still be baixa (short-circuit absolute)."""
    with patch(
        "app.integrations.email_classifier._load_learned_senders",
        return_value=frozenset({"vip@parceiro.com"}),
    ):
        email = _make(
            subject="Newsletter semanal",
            snippet="Para descadastrar clique em unsubscribe.",
            sender="vip@parceiro.com",
        )
        clf = classify_email(email)
    assert clf.category == "newsletter"
    assert clf.priority == "baixa"
    assert "IMPORTANT_SENDER_LEARNED" not in clf.audit_tags


def test_learned_sender_fallback_when_empty():
    """When learning list is empty, no IMPORTANT_SENDER_LEARNED tag must be emitted."""
    with patch(
        "app.integrations.email_classifier._load_learned_senders",
        return_value=frozenset(),
    ):
        email = _make(subject="Reunião comercial amanhã", sender="qualquer@empresa.com")
        clf = classify_email(email)
    assert "IMPORTANT_SENDER_LEARNED" not in clf.audit_tags


def test_learned_and_human_sender_both_tagged():
    """Named sender that is also learned must receive both IMPORTANT_SENDER_LEARNED and IMPORTANT_SENDER."""
    with patch(
        "app.integrations.email_classifier._load_learned_senders",
        return_value=frozenset({"vip@parceiro.com"}),
    ):
        email = _make(subject="Proposta", sender="Ana VIP <vip@parceiro.com>")
        clf = classify_email(email)
    assert "IMPORTANT_SENDER_LEARNED" in clf.audit_tags
    assert "IMPORTANT_SENDER" in clf.audit_tags
    assert "learned_sender" in clf.score_reasons
    assert "human_sender" in clf.score_reasons


def test_learned_sender_short_reason_maps_correctly():
    """IMPORTANT_SENDER_LEARNED must resolve to 'Remetente prioritário' via build_short_reason."""
    from app.integrations.email_classifier import build_short_reason

    assert build_short_reason(["IMPORTANT_SENDER_LEARNED"]) == "Remetente prioritário"
