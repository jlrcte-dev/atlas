"""Scope gate for news pipeline — Hybrid Filter v2 (V3.2 calibration).

Determines whether a news item is relevant enough to enter the classification
pipeline. Five layers define scope, evaluated in order:

  Group A — Tracked assets (portfolio + sector leaders):
    Petrobras, Vale, Ambev, Itaúsa, Ibovespa, plus the major B3 tickers
    in banking/energy/retail/airlines that drive index movement.

  Group B — Macro / market / commodities:
    Selic, Copom, Banco Central, juros, inflação, câmbio, dólar,
    petróleo, minério, soja, ouro, bolsa, ações, mercado financeiro,
    PIB, fiscal, dívida pública, etc.

  Group C — Geopolitical / social with material market impact:
    Conservative: only terms with clear economic spillover.

  Group D — Strategic tech / business AI (V3.2 addition):
    OpenAI, Nvidia, big tech, semicondutores, inteligência artificial,
    cibersegurança, cloud — relevant for business/tech investment.

  Fallback — `relevant` (V3.2 addition):
    When none of the explicit groups match, accept the item if it carries
    at least one strong relevance signal (market/economic/policy impact or
    a strong-signal term such as "crise", "default") AND is not noise.
    This catches in-domain articles whose surface terms differ from the
    curated lists, without opening the gate to entertainment/lifestyle.

Public API:
  evaluate_scope(normalized_text) -> (bool, str | None)

    (True,  "tracked_asset")     — matched Group A
    (True,  "macro")              — matched Group B
    (True,  "geopolitical")       — matched Group C
    (True,  "strategic")          — matched Group D
    (True,  "fallback_relevant")  — passed via classifier impact signals
    (False, None)                 — out of scope; caller should discard item

Normalization contract:
  Caller is responsible for normalizing text via _normalize_text before
  passing it here. This module does not re-normalize.

Design notes:
  - All patterns are compiled once at module load (single pass per call).
  - Terms are sorted by length descending to give precedence to phrases
    over substrings in the alternation.
  - No word boundaries: semantically equivalent to `t in text` substring
    matching, consistent with news_classifier convention.
  - Fallback reuses the already-compiled impact patterns from
    news_classifier — no duplication, no extra dependency.
"""
from __future__ import annotations

import re

from app.integrations.news_classifier import (
    _ECONOMIC_IMPACT_RE,
    _MARKET_IMPACT_RE,
    _NOISE_RE,
    _POLICY_IMPACT_RE,
    _STRONG_SIGNAL_RE,
)


# ── Pattern builder ───────────────────────────────────────────────────────────

def _build_scope_pattern(terms: list[str]) -> re.Pattern[str]:
    """Compile a list of scope terms into a single alternation regex.

    Terms sorted by length descending so that multi-word phrases
    are attempted before any shared substrings.
    """
    escaped = [re.escape(t) for t in sorted(terms, key=len, reverse=True)]
    return re.compile('|'.join(escaped), re.IGNORECASE)


# ── Group A: Tracked assets + sector leaders ──────────────────────────────────

_GROUP_A_TERMS: list[str] = [
    # Petrobras
    "petrobras", "petr3", "petr4",
    # Ambev
    "ambev", "abev3",
    # Itaúsa — both accented and ASCII variants
    "itaúsa", "itausa", "itsa4",
    # Vale — "vale3" is unambiguous; bare "vale" covered with documented caveat
    "vale3", "vale",
    # Ibovespa / broad market index
    "ibovespa", "ibov", "bovespa",
    # Major banks (high index weight)
    "itaú", "itau", "itub4",
    "bradesco", "bbdc4", "bbdc3",
    "banco do brasil", "bbas3",
    "santander", "sanb11",
    "btg pactual", "btgp4",
    # Energy (beyond Petrobras)
    "eletrobras", "elet3", "elet6",
    # Retail / consumer
    "magazine luiza", "magalu", "magalu3", "mglu3",
    "via varejo", "viia3",
    "lojas renner", "lren3",
    # Airlines
    "azul", "azul4", "gol", "goll4",
    # Iron ore / mining majors beyond Vale
    "csn", "csna3", "usiminas", "usim5", "gerdau", "ggbr4",
    # Beef / agro
    "jbs", "jbss3", "marfrig", "mrfg3", "brf", "brfs3",
    # Telecom
    "vivo", "telefonica", "vivt3",
]

_GROUP_A_RE: re.Pattern[str] = _build_scope_pattern(_GROUP_A_TERMS)


# ── Group B: Macro / market / commodities ─────────────────────────────────────

_GROUP_B_TERMS: list[str] = [
    # Multi-word phrases (length sort handles ordering, listed for clarity)
    "política monetária", "politica monetaria",
    "política fiscal", "politica fiscal",
    "arcabouço fiscal", "arcabouco fiscal",
    "dívida pública", "divida publica",
    "minério de ferro", "minerio de ferro",
    "banco central", "banco central europeu",
    "mercado financeiro", "mercado de capitais",
    "renda variável", "renda variavel",
    "renda fixa", "tesouro direto",
    "balança comercial", "balanca comercial",
    "reservas internacionais",
    "taxa de juros",
    "reforma tributária", "reforma tributaria",
    "reforma da previdência", "reforma da previdencia",
    "medida provisória", "medida provisoria",
    "imposto de renda",
    "ministério da fazenda", "ministerio da fazenda",
    "ministério da economia", "ministerio da economia",
    # Institutions and benchmarks
    "bacen", "copom", "selic", "ipca", "igpm", "igp-m", "fed", "federal reserve",
    "fmi", "ocde", "bndes", "cvm", "receita federal",
    # Indicators — accented + ASCII
    "inflação", "inflacao",
    "deflação", "deflacao",
    "câmbio", "cambio",
    "petróleo", "petroleo",
    "déficit", "deficit",
    "superávit", "superavit",
    "dólar", "dolar",
    "pib", "recessão", "recessao", "desemprego",
    # Equity / market
    "bolsa", "ações", "acoes", "b3", "ipo",
    "dividendos", "dividendo", "valuation",
    "fundos imobiliários", "fundos imobiliarios", "fii",
    # Commodities
    "commodities", "commodity", "soja", "milho", "café", "cafe",
    "ouro", "minério", "minerio", "açúcar", "acucar",
    # Generic but high-signal in financial context
    "juros",
    # Regulation explicitly relevant to markets
    "regulação financeira", "regulacao financeira",
    "lei das estatais", "open finance",
]

_GROUP_B_RE: re.Pattern[str] = _build_scope_pattern(_GROUP_B_TERMS)


# ── Group C: Geopolitical / social with material market impact ────────────────
# Conservative by design — only terms with clear economic/market spillover.

_GROUP_C_TERMS: list[str] = [
    # Specific geopolitical events
    "conflito internacional",
    "crise institucional",
    "bloqueio logístico", "bloqueio logistico",
    "choque de oferta",
    # Sanctions and embargoes
    "sanções econômicas", "sancoes economicas",
    "sanções", "sancoes",
    "embargo",
    # War / conflict (broad but high signal in financial news context)
    "guerra",
    # Labor disruption with supply chain impact
    "greve",
    # Trade conflict (V3.2)
    "tarifas comerciais", "tarifa comercial",
    "guerra comercial",
    "barreira comercial",
]

_GROUP_C_RE: re.Pattern[str] = _build_scope_pattern(_GROUP_C_TERMS)


# ── Group D: Strategic tech / business AI (V3.2) ──────────────────────────────
# Captures tech news with clear business/investment relevance. Excludes
# generic "internet", "app" terms to avoid lifestyle/consumer-tech drift.

_GROUP_D_TERMS: list[str] = [
    # AI players & products
    "openai", "chatgpt", "claude", "anthropic", "gemini", "google deepmind",
    "nvidia", "nvda",
    "microsoft", "msft", "azure",
    "alphabet", "googl", "google cloud",
    "meta platforms", "meta ai",
    "amazon web services", "aws",
    "apple", "aapl",
    # Semis / hardware
    "semicondutor", "semicondutores", "chip", "chips", "tsmc", "asml",
    # Concepts with business weight
    "inteligência artificial", "inteligencia artificial",
    "ia generativa", "ai generativa", "generative ai",
    "computação em nuvem", "computacao em nuvem", "cloud computing",
    "cibersegurança", "ciberseguranca", "cybersegurança", "cyberseguranca",
    "transformação digital", "transformacao digital",
    "big tech",
]

_GROUP_D_RE: re.Pattern[str] = _build_scope_pattern(_GROUP_D_TERMS)


# ── Fallback impact gate ──────────────────────────────────────────────────────

def _has_relevance_signal(text: str) -> bool:
    """Return True if text carries any classifier-grade impact signal.

    Reuses the already-compiled patterns from news_classifier so the fallback
    aligns with the same lexicon used to score articles downstream. Each
    pattern is high-quality (curated finance/policy language), so a single
    match is sufficient evidence of in-domain content.
    """
    return (
        bool(_MARKET_IMPACT_RE.search(text))
        or bool(_ECONOMIC_IMPACT_RE.search(text))
        or bool(_POLICY_IMPACT_RE.search(text))
        or bool(_STRONG_SIGNAL_RE.search(text))
    )


# ── Public API ────────────────────────────────────────────────────────────────

def evaluate_scope(normalized_text: str) -> tuple[bool, str | None]:
    """Evaluate whether a news item is in scope for the news pipeline.

    Args:
        normalized_text: text already processed by _normalize_text
                         (lowercase, punctuation stripped, whitespace collapsed).

    Returns:
        (True,  "tracked_asset")     — matched Group A (portfolio / sector leader)
        (True,  "macro")             — matched Group B (monetary/fiscal/market)
        (True,  "geopolitical")      — matched Group C (geo/social with market impact)
        (True,  "strategic")         — matched Group D (strategic tech / business AI)
        (True,  "fallback_relevant") — no group matched but classifier-grade
                                       impact signal present and item is not noise
        (False, None)                — out of scope; caller should discard item

    Order:
        Explicit groups (A→B→C→D) take precedence over the fallback so that
        the most specific reason is returned for auditability.
    """
    if _GROUP_A_RE.search(normalized_text):
        return True, "tracked_asset"
    if _GROUP_B_RE.search(normalized_text):
        return True, "macro"
    if _GROUP_C_RE.search(normalized_text):
        return True, "geopolitical"
    if _GROUP_D_RE.search(normalized_text):
        return True, "strategic"

    # Controlled fallback: must carry a real impact signal AND not be noise.
    # _NOISE check here is fail-fast — the classifier will reject noise later
    # anyway, but blocking it here keeps fallback_relevant a clean signal.
    if _has_relevance_signal(normalized_text) and not _NOISE_RE.search(normalized_text):
        return True, "fallback_relevant"

    return False, None
