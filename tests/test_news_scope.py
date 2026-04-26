"""Tests for the news scope gate (V3.2 calibration).

Covers:
  - explicit groups A/B/C/D positive matches
  - controlled fallback_relevant via impact signals
  - negatives: lifestyle / clickbait / generic entertainment must stay out
  - noise must not be admitted via fallback
  - integration with summarize_news (contract preserved)
"""
from __future__ import annotations

from app.integrations.news_classifier import _normalize_text
from app.integrations.tracked_scope import evaluate_scope


def _scope(title: str, summary: str = "") -> tuple[bool, str | None]:
    return evaluate_scope(_normalize_text(f"{title} {summary}"))


# ── Group A — tracked assets / sector leaders ────────────────────────────────

def test_group_a_petrobras_passes():
    in_scope, reason = _scope("Petrobras anuncia novo plano de investimentos")
    assert in_scope
    assert reason == "tracked_asset"


def test_group_a_bradesco_lucro_passes():
    # User explicitly listed lucro / bancos as interest
    in_scope, reason = _scope("Lucro do Bradesco sobe 10% no trimestre")
    assert in_scope
    assert reason == "tracked_asset"


def test_group_a_magalu_passes():
    in_scope, reason = _scope("Magazine Luiza apresenta resultado trimestral")
    assert in_scope
    assert reason == "tracked_asset"


# ── Group B — macro / market / commodities ────────────────────────────────────

def test_group_b_acoes_bolsa_passes():
    in_scope, reason = _scope("Bolsa fecha em alta com investidores otimistas")
    assert in_scope
    assert reason == "macro"


def test_group_b_petroleo_passes():
    in_scope, reason = _scope("Preço do petróleo dispara após decisão da OPEP")
    assert in_scope
    assert reason == "macro"


def test_group_b_reforma_tributaria_passes():
    in_scope, reason = _scope("Reforma tributária aprovada na Câmara dos Deputados")
    assert in_scope
    assert reason == "macro"


def test_group_b_pib_passes():
    in_scope, reason = _scope("PIB do Brasil cresce 2,5% no terceiro trimestre")
    assert in_scope
    assert reason == "macro"


# ── Group C — geopolítica ────────────────────────────────────────────────────

def test_group_c_guerra_passes():
    in_scope, reason = _scope("Guerra na Ucrânia entra em novo capítulo")
    assert in_scope
    assert reason == "geopolitical"


def test_group_c_tarifas_comerciais_passes():
    in_scope, reason = _scope("Tarifas comerciais americanas afetam exportadores")
    assert in_scope
    assert reason == "geopolitical"


# ── Group D — tecnologia estratégica ─────────────────────────────────────────

def test_group_d_nvidia_chip_passes():
    in_scope, reason = _scope("Nvidia anuncia novo chip de inteligência artificial")
    assert in_scope
    assert reason == "strategic"


def test_group_d_openai_passes():
    in_scope, reason = _scope("OpenAI lança novo modelo de IA generativa")
    assert in_scope
    assert reason == "strategic"


def test_group_d_ciberseguranca_passes():
    in_scope, reason = _scope("Cibersegurança vira prioridade para empresas brasileiras")
    assert in_scope
    assert reason == "strategic"


# ── Fallback — sinais de impacto sem termo dos grupos ────────────────────────

def test_fallback_strong_signal_default_passes():
    # "default" is a strong-signal term but no Group A/B/C/D term present
    in_scope, reason = _scope("Empresa entra em default após calote bilionário")
    assert in_scope
    assert reason == "fallback_relevant"


def test_fallback_policy_impact_decreto_passes():
    in_scope, reason = _scope("Decreto sancionado regulamenta novo setor")
    assert in_scope
    assert reason == "fallback_relevant"


# ── Negatives — fora de escopo ───────────────────────────────────────────────

def test_lifestyle_celebrity_dropped():
    in_scope, reason = _scope("Famosa atriz lança nova coleção de roupas")
    assert not in_scope
    assert reason is None


def test_sports_dropped():
    in_scope, reason = _scope("Time vence campeonato após pênaltis emocionantes")
    assert not in_scope
    assert reason is None


def test_entertainment_dropped():
    in_scope, reason = _scope("Filme bate recorde de bilheteria no fim de semana")
    assert not in_scope
    assert reason is None


def test_health_general_dropped():
    in_scope, reason = _scope("Estudo aponta benefícios da meditação para o sono")
    assert not in_scope
    assert reason is None


# ── Fallback não libera ruído ────────────────────────────────────────────────

def test_fallback_blocks_noise_clickbait():
    # Has impact term ("crise") but is clickbait — must stay out
    in_scope, reason = _scope(
        "Veja como esta crise vai mudar tudo",
        "Clique aqui e confira agora",
    )
    assert not in_scope, f"clickbait com sinal de impacto vazou via fallback (reason={reason})"


def test_fallback_blocks_promo_with_impact_word():
    # "Crise" + promo language — fallback must reject
    in_scope, reason = _scope(
        "Oferta especial em meio à crise: aproveite a oferta",
    )
    assert not in_scope
    assert reason is None


# ── Integration with summarize_news (contract preserved) ─────────────────────

def test_summarize_news_contract_preserved():
    from app.modules.briefing.news_service import NewsService

    result = NewsService().summarize_news()
    # Contract: keys unchanged, types unchanged
    assert set(result.keys()) >= {"total", "categories", "by_category", "items", "summary"}
    assert isinstance(result["total"], int)
    assert isinstance(result["categories"], dict)
    assert isinstance(result["items"], list)
    assert isinstance(result["summary"], str)
    # Total bounded by curation cap (5)
    assert 0 <= result["total"] <= 5
