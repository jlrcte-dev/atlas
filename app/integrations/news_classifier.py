"""Deterministic news article classifier.

classify_news(title, summary, source) -> NewsClassification

Decision order (mandatory):
  1. Detect flags (including noise candidate)
  2. Infer category — noise short-circuits to "ruido" immediately
  3. Score from flags + category + title signals
  4. Derive priority from score via calibrated thresholds

No external dependencies. No LLM. Purely deterministic.

Performance note:
  All frozenset term sets are compiled into alternation regexes at module
  load time (_build_pattern). Each classification call executes a single
  regex search per signal group instead of iterating the full set, reducing
  per-call cost from O(n×m) to approximately O(m) where m = text length.
"""
from __future__ import annotations

import re
from typing import TypedDict


# ── Result types ──────────────────────────────────────────────────────────────

class NewsFlags(TypedDict):
    has_market_impact: bool
    has_economic_impact: bool
    has_policy_impact: bool
    has_strong_signal: bool
    has_numbers: bool
    is_duplicate_candidate: bool
    is_noise_candidate: bool


class NewsClassification(TypedDict):
    category: str           # macro | mercado | empresas | tecnologia | politica | internacional | setorial | ruido
    flags: NewsFlags
    score: int
    priority: str           # high | medium | low
    score_reasons: list[str]


# ── Signal sets ───────────────────────────────────────────────────────────────

_MACRO: frozenset[str] = frozenset({
    "pib", "inflação", "inflacao", "juros", "selic", "ipca", "igpm",
    "desemprego", "recessão", "recessao", "crescimento econômico", "crescimento economico",
    "balança comercial", "balanca comercial", "câmbio", "cambio",
    "taxa de juros", "banco central", "bacen", "federal reserve", "fed",
    "ocde", "fmi", "banco mundial", "déficit fiscal", "deficit fiscal",
    "superávit", "superavit", "política monetária", "politica monetaria",
    "dólar", "dolar", "reservas internacionais",
})

_MERCADO: frozenset[str] = frozenset({
    "bolsa", "ibovespa", "b3", "ações", "acoes", "fundos",
    "commodities", "petróleo", "petroleo", "minério", "minerio",
    "ouro", "bitcoin", "cripto", "criptomoeda", "renda fixa",
    "tesouro direto", "dividendo", "valuation", "ipo",
    "spread", "crédito", "credito", "mercado financeiro",
    "mercado de capitais", "pré-mercado", "pre-mercado",
})

_POLITICA: frozenset[str] = frozenset({
    "governo", "presidente", "ministério", "ministerio", "congresso",
    "senado", "câmara dos deputados", "camara dos deputados",
    "deputado", "senador", "eleição", "eleicao", "partido político",
    "partido politico", "reforma tributária", "reforma tributaria",
    "legislação", "legislacao", "decreto", "medida provisória", "medida provisoria",
    "stf", "judiciário", "judiciario", "política pública", "politica publica",
    "regulação", "regulacao", "regulamentação", "regulamentacao",
    "lula", "bolsonaro", "ministro da fazenda", "ministro da economia",
})

_INTERNACIONAL: frozenset[str] = frozenset({
    "eua", "estados unidos", "china", "europa", "brics", "g20", "g7",
    "guerra", "sanção", "sancao", "geopolítica", "geopolitica",
    "trump", "xi jinping", "tarifas comerciais",
    "exportação", "exportacao", "importação", "importacao",
    "mercado global", "mercado mundial", "economia global",
    "banco central europeu", "reserva federal",
})

_EMPRESAS: frozenset[str] = frozenset({
    "aquisição", "aquisicao", "fusão", "fusao", "merger",
    "resultado trimestral", "resultado anual", "lucro líquido", "lucro liquido",
    "prejuízo", "prejuizo", "receita líquida", "receita liquida", "faturamento",
    "ceo", "conselho de administração", "conselho de administracao",
    "s.a.", "holding", "demissão em massa", "demissao em massa",
    "layoff", "reestruturação", "reestruturacao", "ipo", "oferta pública",
})

_TECNOLOGIA: frozenset[str] = frozenset({
    "inteligência artificial", "inteligencia artificial",
    "machine learning", "deep learning",
    "cybersegurança", "cyberseguranca", "segurança digital",
    "computação em nuvem", "computacao em nuvem",
    "big tech", "openai", "chatgpt", "gemini",
    "chip", "semicondutor", "inovação tecnológica", "inovacao tecnologica",
    "fintech", "edtech", "healthtech",
    "transformação digital", "transformacao digital",
})

_SETORIAL: frozenset[str] = frozenset({
    "agronegócio", "agronegocio", "agropecuária", "agropecuaria",
    "saúde pública", "saude publica", "sistema de saúde", "sistema de saude",
    "educação básica", "educacao basica", "ensino superior",
    "infraestrutura", "saneamento", "habitação", "habitacao",
    "energia elétrica", "energia eletrica", "petróleo e gás", "petroleo e gas",
    "construção civil", "construcao civil",
    "varejo", "logística", "logistica", "transporte",
    "setor bancário", "setor bancario",
})

# ── Flag signal sets ──────────────────────────────────────────────────────────

_MARKET_IMPACT: frozenset[str] = frozenset({
    "bolsa", "ibovespa", "ações", "acoes", "b3", "commodities",
    "câmbio", "cambio", "dólar", "dolar", "petróleo", "petroleo",
    "juros", "selic", "spread", "crédito", "credito",
    "mercado financeiro", "renda variável", "renda variavel",
})

_ECONOMIC_IMPACT: frozenset[str] = frozenset({
    "pib", "inflação", "inflacao", "crescimento", "recessão", "recessao",
    "emprego", "desemprego", "balança comercial", "balanca comercial",
    "exportação", "exportacao", "importação", "importacao",
    "déficit", "deficit", "fiscal", "arrecadação", "arrecadacao",
})

_POLICY_IMPACT: frozenset[str] = frozenset({
    "reforma", "decreto", "regulação", "regulacao",
    "regulamentação", "regulamentacao", "medida provisória", "medida provisoria",
    "portaria", "resolução", "resolucao", "norma",
    "aprovado", "vetado", "sancionado", "publicado no diário oficial",
})

# ── Quality entity set (Phase B.2) — used only by compute_quality_score ──────
# Named institutions/indices that signal a concrete, attributable news event.

_QUALITY_ENTITIES: frozenset[str] = frozenset({
    # Monetary policy
    "bacen", "banco central", "fed", "federal reserve", "reserva federal",
    "banco central europeu", "fmi", "banco mundial", "ocde",
    # Market benchmarks
    "ibovespa", "b3", "selic", "ipca",
    # Brazilian government institutions
    "receita federal", "ministerio da fazenda", "ministerio da economia",
    "banco do brasil", "bndes", "cvm",
    # Political institutions
    "stf", "supremo tribunal federal", "congresso", "senado",
    "camara dos deputados",
    # Major companies (representative, not exhaustive)
    "petrobras", "vale", "embraer", "itau", "bradesco", "ambev", "eletrobras",
    # Key figures
    "trump", "lula", "haddad", "campos neto",
    # International entities
    "eua", "estados unidos", "china", "opep",
})

_STRONG_SIGNAL: frozenset[str] = frozenset({
    "crise", "colapso", "falência", "falencia", "default",
    "risco sistêmico", "risco sistemico", "calote",
    "acordo histórico", "acordo historico", "decisão histórica", "decisao historica",
    "suspensão", "suspensao", "bloqueio", "intervenção", "intervencao",
    "quebra", "bancarrota", "emergência", "emergencia",
})

_NOISE: frozenset[str] = frozenset({
    "clique aqui", "veja também", "veja tambem", "leia mais", "saiba mais",
    "confira agora", "você precisa", "voce precisa",
    "imperdível", "imperdivel", "inacreditável", "inacreditavel",
    "chocante", "viral", "rumor", "boato",
    "especulação", "especulacao", "patrocinado", "publicidade",
    "oferta especial", "oferta com desconto", "desconto imperdível",
    "desconto imperdivel", "cupom",
    # Hard-junk additions (Phase B)
    "veja como",        # clickbait phrase
    "descubra como",    # clickbait phrase (safer than bare "descubra")
    "descubra agora",   # clickbait phrase
    "publipost",        # sponsored content
    "publieditorial",   # sponsored content
    "promoção especial", "promocao especial",  # promo junk (phrase avoids false positives)
    "aproveite a oferta", "oferta imperdível", "oferta imperdivel",  # promo junk
})

# ── Low-quality signal sets (Phase B.1) ──────────────────────────────────────
# Used exclusively by is_low_quality(). Articles matching these are dropped
# before classify_news() is called — they never receive a score.

_LOW_QUALITY_RECYCLED: frozenset[str] = frozenset({
    "relembre", "tbt", "ano passado", "em arquivo",
    "retrospectiva", "há um ano", "ha um ano", "de volta ao passado",
})

_LOW_QUALITY_LISTICLE: frozenset[str] = frozenset({
    "dicas para", "passo a passo", "maneiras de",
    "guia para", "guia completo",
    "o que é", "o que e", "como funciona",
    "entenda como", "tudo sobre", "o que saber sobre",
})

_LOW_QUALITY_GOSSIP: frozenset[str] = frozenset({
    "entenda o caso", "saiba quem", "quem é o", "quem e o",
    "polêmica", "polemica", "briga entre",
})

_LISTICLE_NUMBER_RE: re.Pattern[str] = re.compile(
    r'\b\d+\s+(?:motivos|raz[oõ]es|dicas|maneiras|formas|passos)\b',
    re.IGNORECASE,
)

_VAGUE_TITLE: frozenset[str] = frozenset({
    "destaques", "resumo do dia", "manchetes", "boletim",
    "notícias de hoje", "noticias de hoje", "o que aconteceu",
    "confira os destaques", "principais notícias", "principais noticias",
    "top notícias", "top noticias", "destaques do dia",
})

_ECONOMIC_NUMBER_RE = re.compile(
    r'r\$\s*\d'                          # R$ followed by digit: R$100, R$ 3,5
    r'|\$\s*\d'                          # $ followed by digit:  $50
    r'|\d[\d.,]*\s*(?:'                  # digit followed by economic marker:
    r'%|bps\b|bi\b|mi\b|tri\b'          #   %, bps, bi/mi/tri abbreviations
    r'|bilh[oõ]|milh[oõ]|trilh[oõ]'    #   bilhões/milhões/trilhões (any gender/number)
    r'|pontos[- ]base'                   #   pontos-base
    r')',
    re.IGNORECASE,
)

# ── Category priority order ───────────────────────────────────────────────────

_CATEGORY_PRIORITY: list[tuple[str, frozenset[str]]] = [
    ("macro", _MACRO),
    ("mercado", _MERCADO),
    ("politica", _POLITICA),
    ("internacional", _INTERNACIONAL),
    ("empresas", _EMPRESAS),
    ("tecnologia", _TECNOLOGIA),
    ("setorial", _SETORIAL),
]

# ── Score model — single source of calibration ────────────────────────────────

SCORE_WEIGHTS: dict[str, int] = {
    "has_market_impact": 3,
    "has_economic_impact": 3,
    "has_policy_impact": 2,
    "has_strong_signal": 2,
    # has_numbers intentionally excluded: numeric presence alone is not a relevance signal;
    # numbers only matter when paired with impact flags (which already carry the weight)
    "is_noise_candidate": -3,
}

CATEGORY_SCORE: dict[str, int] = {
    "macro": 2,
    "mercado": 2,
    "empresas": 1,
    "politica": 1,
    "internacional": 1,
    "tecnologia": 1,
    "setorial": 0,
    "ruido": -3,
}

SCORE_THRESHOLD_HIGH: int = 8   # Phase B: raised from 6 — requires multi-signal evidence
SCORE_THRESHOLD_MEDIUM: int = 4  # Phase B: raised from 3 — reduces low-value medium items


# ── Text normalization ────────────────────────────────────────────────────────

_PUNCT_STRIP_RE: re.Pattern[str] = re.compile(r'[^\w\s]')
_SPACE_COLLAPSE_RE: re.Pattern[str] = re.compile(r'\s+')


def _normalize_text(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace, strip edges.

    Exported for reuse in news_service (dedup key generation).
    Semantically equivalent to the former _normalize_title in news_service.
    """
    stripped = _PUNCT_STRIP_RE.sub('', text.lower())
    return _SPACE_COLLAPSE_RE.sub(' ', stripped).strip()


# ── Pattern builder ───────────────────────────────────────────────────────────

def _build_pattern(terms: frozenset[str]) -> re.Pattern[str]:
    """Compile a frozenset of terms into a single alternation regex.

    Terms are sorted by length (longest first) so that multi-word phrases
    are attempted before their substrings in the alternation.

    No word boundaries (\b) are added — matching is intentionally
    substring-based to preserve semantic equivalence with the original
    `t in text` approach. Terms that contain non-alphanumeric characters
    (e.g. "s.a.", "pré-mercado") are handled safely via re.escape.
    """
    escaped = [re.escape(t) for t in sorted(terms, key=len, reverse=True)]
    return re.compile('|'.join(escaped), re.IGNORECASE)


# ── Compiled patterns (module-level — built once at import time) ──────────────

_MACRO_RE: re.Pattern[str] = _build_pattern(_MACRO)
_MERCADO_RE: re.Pattern[str] = _build_pattern(_MERCADO)
_POLITICA_RE: re.Pattern[str] = _build_pattern(_POLITICA)
_INTERNACIONAL_RE: re.Pattern[str] = _build_pattern(_INTERNACIONAL)
_EMPRESAS_RE: re.Pattern[str] = _build_pattern(_EMPRESAS)
_TECNOLOGIA_RE: re.Pattern[str] = _build_pattern(_TECNOLOGIA)
_SETORIAL_RE: re.Pattern[str] = _build_pattern(_SETORIAL)

_MARKET_IMPACT_RE: re.Pattern[str] = _build_pattern(_MARKET_IMPACT)
_ECONOMIC_IMPACT_RE: re.Pattern[str] = _build_pattern(_ECONOMIC_IMPACT)
_POLICY_IMPACT_RE: re.Pattern[str] = _build_pattern(_POLICY_IMPACT)
_STRONG_SIGNAL_RE: re.Pattern[str] = _build_pattern(_STRONG_SIGNAL)
_NOISE_RE: re.Pattern[str] = _build_pattern(_NOISE)

_QUALITY_ENTITIES_RE: re.Pattern[str] = _build_pattern(_QUALITY_ENTITIES)
_LOW_QUALITY_RECYCLED_RE: re.Pattern[str] = _build_pattern(_LOW_QUALITY_RECYCLED)
_LOW_QUALITY_LISTICLE_RE: re.Pattern[str] = _build_pattern(_LOW_QUALITY_LISTICLE)
_LOW_QUALITY_GOSSIP_RE: re.Pattern[str] = _build_pattern(_LOW_QUALITY_GOSSIP)
_VAGUE_TITLE_RE: re.Pattern[str] = _build_pattern(_VAGUE_TITLE)

# ── Category pattern list — mirrors _CATEGORY_PRIORITY with compiled patterns ─

_CATEGORY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("macro", _MACRO_RE),
    ("mercado", _MERCADO_RE),
    ("politica", _POLITICA_RE),
    ("internacional", _INTERNACIONAL_RE),
    ("empresas", _EMPRESAS_RE),
    ("tecnologia", _TECNOLOGIA_RE),
    ("setorial", _SETORIAL_RE),
]


# ── Public API ────────────────────────────────────────────────────────────────

def classify_news(title: str, summary: str, source: str) -> NewsClassification:
    """Classify a news article deterministically.

    Falls back to setorial + score=0 + priority=low on any unexpected error.
    """
    try:
        return _do_classify(title, summary, source)
    except Exception:
        return {
            "category": "setorial",
            "flags": {
                "has_market_impact": False,
                "has_economic_impact": False,
                "has_policy_impact": False,
                "has_strong_signal": False,
                "has_numbers": False,
                "is_duplicate_candidate": False,
                "is_noise_candidate": False,
            },
            "score": 0,
            "priority": "low",
            "score_reasons": ["fallback"],
        }


def compute_quality_score(title: str, summary: str) -> int:
    """Return a ranking quality modifier (0-2). Does NOT affect priority.

    2 — specific event: named institution/entity + quantitative claim or concrete action
    1 — relevant but generic: market/economic context with at least one specificity signal
    0 — borderline: valid but weakly signaled; sorts last among peers

    Called per-item during sort; does not replace or modify the base score.
    """
    text = f"{title} {summary}".lower()

    has_economic_number = bool(_ECONOMIC_NUMBER_RE.search(text))
    has_named_entity = bool(_QUALITY_ENTITIES_RE.search(text))
    has_concrete_action = (
        bool(_STRONG_SIGNAL_RE.search(text))
        or bool(_POLICY_IMPACT_RE.search(text))
    )
    has_impact = (
        bool(_MARKET_IMPACT_RE.search(text))
        or bool(_ECONOMIC_IMPACT_RE.search(text))
    )

    if has_named_entity and (has_economic_number or has_concrete_action):
        return 2

    if has_impact and (has_economic_number or has_named_entity or has_concrete_action):
        return 1

    return 0


def is_low_quality(title: str, summary: str) -> bool:
    """Return True if the article should be excluded before scoring.

    Checks (title-only for structural patterns, full text for contextual):
    - Short title (< 4 words)
    - Recycled / historical content
    - Listicle / generic how-to / explainer without concrete news event
    - "N motivos/dicas/maneiras/passos" pattern
    - Clickbait / gossip headline
    - "oferta" or "promoção" without financial/political context
    """
    text = f"{title} {summary}".lower()
    title_lower = title.lower()

    if len(title_lower.split()) < 4:
        return True

    if _LOW_QUALITY_RECYCLED_RE.search(text):
        return True

    # Listicle/explainer: check title only to avoid false positives in summaries
    if _LOW_QUALITY_LISTICLE_RE.search(title_lower):
        return True

    if _LISTICLE_NUMBER_RE.search(title_lower):
        return True

    # Gossip/clickbait: title only
    if _LOW_QUALITY_GOSSIP_RE.search(title_lower):
        return True

    # "oferta"/"promoção" without economic, market, or political context → promo junk
    has_promo_word = (
        "oferta" in title_lower
        or "promoção" in title_lower
        or "promocao" in title_lower
    )
    if has_promo_word:
        has_context = (
            bool(_MARKET_IMPACT_RE.search(text))
            or bool(_ECONOMIC_IMPACT_RE.search(text))
            or bool(_POLITICA_RE.search(text))
        )
        if not has_context:
            return True

    return False


# ── Private helpers ───────────────────────────────────────────────────────────

def _do_classify(title: str, summary: str, source: str) -> NewsClassification:
    text = f"{title} {summary}".lower()
    title_lower = title.lower()

    flags = _detect_news_flags(text, title_lower)
    category = _infer_news_category(text, flags["is_noise_candidate"])
    score, score_reasons = _score_news(flags, category, title_lower)
    priority = _derive_priority_from_score(score)

    return {
        "category": category,
        "flags": flags,
        "score": score,
        "priority": priority,
        "score_reasons": score_reasons,
    }


def _infer_news_category(text: str, is_noise: bool) -> str:
    """Infer category from text using compiled alternation patterns (single pass each)."""
    if is_noise:
        return "ruido"
    for category, pattern in _CATEGORY_PATTERNS:
        if pattern.search(text):
            return category
    # TODO: [V4] use embedding similarity for ambiguous articles that fall through to setorial
    return "setorial"


def _detect_news_flags(text: str, title_lower: str) -> NewsFlags:
    """Detect operational flags using compiled alternation patterns."""
    is_noise = (
        bool(_NOISE_RE.search(text))
        or len(title_lower.split()) < 3
    )

    return {
        "has_market_impact": bool(_MARKET_IMPACT_RE.search(text)),
        "has_economic_impact": bool(_ECONOMIC_IMPACT_RE.search(text)),
        "has_policy_impact": bool(_POLICY_IMPACT_RE.search(text)),
        "has_strong_signal": bool(_STRONG_SIGNAL_RE.search(text)),
        "has_numbers": bool(_ECONOMIC_NUMBER_RE.search(text)),
        "is_duplicate_candidate": False,
        "is_noise_candidate": is_noise,
    }


def _score_news(flags: NewsFlags, category: str, title_lower: str) -> tuple[int, list[str]]:
    """Compute deterministic score from flags, category bonus, and title signals.

    score_reasons format: "+N signal_name" or "-N signal_name" for auditability.
    Each reason appears at most once. No external dependencies.
    """
    score = 0
    reasons: list[str] = []

    for flag, weight in SCORE_WEIGHTS.items():
        if flags.get(flag):
            score += weight
            sign = "+" if weight > 0 else ""
            reasons.append(f"{sign}{weight} {flag}")

    cat_pts = CATEGORY_SCORE.get(category, 0)
    if cat_pts:
        score += cat_pts
        sign = "+" if cat_pts > 0 else ""
        reasons.append(f"{sign}{cat_pts} category_{category}")

    if _VAGUE_TITLE_RE.search(title_lower):
        score -= 2
        reasons.append("-2 vague_title")

    if len(title_lower.split()) < 4:
        score -= 1
        reasons.append("-1 short_title")

    # TODO: [V4] incorporate source credibility scores from a trusted-source registry
    return score, reasons


def _derive_priority_from_score(score: int) -> str:
    if score >= SCORE_THRESHOLD_HIGH:
        return "high"
    if score >= SCORE_THRESHOLD_MEDIUM:
        return "medium"
    return "low"
