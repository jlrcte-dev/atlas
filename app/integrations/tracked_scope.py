"""Scope gate for news pipeline — Hybrid Filter (Mode 3: portfolio_macro_geo).

Determines whether a news item is relevant enough to enter the classification
pipeline. Three groups define the scope:

  Group A — Tracked assets (portfolio):
    Ambev, Itaúsa, Petrobras, Vale, Ibovespa

  Group B — Macro / monetary policy:
    Selic, Copom, Banco Central, juros, inflação, câmbio, dólar,
    petróleo, minério de ferro, política monetária/fiscal, etc.

  Group C — Geopolitical / social with material market impact:
    war, sanctions, international conflict, supply shock, etc.
    Conservative: only terms with clear economic spillover.

Public API:
  evaluate_scope(normalized_text) -> (bool, str | None)

    (True,  "tracked_asset")  — matched Group A
    (True,  "macro")          — matched Group B
    (True,  "geopolitical")   — matched Group C
    (False, None)             — out of scope; item should be dropped

Normalization contract:
  Caller is responsible for normalizing text via _normalize_text before
  passing it here. This module does not re-normalize.

Design notes:
  - All patterns are compiled once at module load (single pass per call).
  - Terms are sorted by length descending to give precedence to phrases
    over substrings in the alternation.
  - No word boundaries: semantically equivalent to `t in text` substring
    matching, consistent with news_classifier convention.
  - "vale" (bare term) is included per spec. Known false-positive risk:
    "vale transporte", "vale refeição". Accepted because Atlas feeds are
    financial-domain sources where this risk is low. "vale3" is the
    unambiguous primary match.
"""
from __future__ import annotations

import re


# ── Pattern builder ───────────────────────────────────────────────────────────

def _build_scope_pattern(terms: list[str]) -> re.Pattern[str]:
    """Compile a list of scope terms into a single alternation regex.

    Terms sorted by length descending so that multi-word phrases
    are attempted before any shared substrings.
    """
    escaped = [re.escape(t) for t in sorted(terms, key=len, reverse=True)]
    return re.compile('|'.join(escaped), re.IGNORECASE)


# ── Group A: Tracked assets ───────────────────────────────────────────────────

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
]

_GROUP_A_RE: re.Pattern[str] = _build_scope_pattern(_GROUP_A_TERMS)


# ── Group B: Macro / monetary policy ─────────────────────────────────────────

_GROUP_B_TERMS: list[str] = [
    # Multi-word phrases first (length sort will handle this, but listed explicitly)
    "política monetária", "politica monetaria",
    "política fiscal", "politica fiscal",
    "arcabouço fiscal", "arcabouco fiscal",
    "dívida pública", "divida publica",
    "minério de ferro", "minerio de ferro",
    "banco central",
    # Institutions and benchmarks
    "bacen", "copom", "selic", "ipca",
    # Economic indicators — accented + ASCII
    "inflação", "inflacao",
    "câmbio", "cambio",
    "petróleo", "petroleo",
    "déficit", "deficit",
    "dólar", "dolar",
    # Generic but high-signal in financial context
    "juros",
]

_GROUP_B_RE: re.Pattern[str] = _build_scope_pattern(_GROUP_B_TERMS)


# ── Group C: Geopolitical / social with material market impact ────────────────
# Conservative by design — only terms with clear economic/market spillover.
# Avoids generic terms ("crise", "problema") that appear without market impact.

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
]

_GROUP_C_RE: re.Pattern[str] = _build_scope_pattern(_GROUP_C_TERMS)


# ── Public API ────────────────────────────────────────────────────────────────

def evaluate_scope(normalized_text: str) -> tuple[bool, str | None]:
    """Evaluate whether a news item is in scope for the portfolio-macro-geo gate.

    Args:
        normalized_text: text already processed by _normalize_text
                         (lowercase, punctuation stripped, whitespace collapsed).

    Returns:
        (True,  "tracked_asset")  — matched Group A (portfolio company or index)
        (True,  "macro")          — matched Group B (monetary/fiscal/economic)
        (True,  "geopolitical")   — matched Group C (geo/social with market impact)
        (False, None)             — out of scope; caller should discard item
    """
    if _GROUP_A_RE.search(normalized_text):
        return True, "tracked_asset"
    if _GROUP_B_RE.search(normalized_text):
        return True, "macro"
    if _GROUP_C_RE.search(normalized_text):
        return True, "geopolitical"
    return False, None
