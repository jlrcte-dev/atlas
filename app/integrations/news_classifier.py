"""Deterministic news article classifier.

classify_news(title, summary, source) -> NewsClassification

Decision order (mandatory):
  1. Detect flags (including noise candidate)
  2. Infer category — noise short-circuits to "ruido" immediately
  3. Score from flags + category + title signals
  4. Derive priority from score via calibrated thresholds

No external dependencies. No LLM. Purely deterministic.
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
})

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
    "has_numbers": 1,
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

SCORE_THRESHOLD_HIGH: int = 6
SCORE_THRESHOLD_MEDIUM: int = 3


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
    """Infer category from text using keyword priority order."""
    if is_noise:
        return "ruido"
    for category, terms in _CATEGORY_PRIORITY:
        if any(t in text for t in terms):
            return category
    # TODO: [V4] use embedding similarity for ambiguous articles that fall through to setorial
    return "setorial"


def _detect_news_flags(text: str, title_lower: str) -> NewsFlags:
    """Detect operational flags using keyword matching."""
    is_noise = (
        any(t in text for t in _NOISE)
        or len(title_lower.split()) < 3
    )

    return {
        "has_market_impact": any(t in text for t in _MARKET_IMPACT),
        "has_economic_impact": any(t in text for t in _ECONOMIC_IMPACT),
        "has_policy_impact": any(t in text for t in _POLICY_IMPACT),
        "has_strong_signal": any(t in text for t in _STRONG_SIGNAL),
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

    if any(t in title_lower for t in _VAGUE_TITLE):
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
