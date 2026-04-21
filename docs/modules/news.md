# Módulo News / RSS — Atlas AI Assistant

> Documentação técnica oficial. Ciclo V1–V4 concluído. Última atualização: Abril 2026.

---

## 1. Visão Geral

**Objetivo:** Transformar feeds RSS brutos em uma lista de notícias classificadas, pontuadas, deduplicadas e ordenadas por relevância, prontas para compor o briefing diário do Atlas.

**Papel dentro do Atlas:** O módulo de notícias é um componente interno do serviço de briefing. Ele não opera como módulo autônomo — suas saídas são consumidas exclusivamente pelo `BriefingService` para compor o relatório diário consolidado junto com dados de inbox e calendário.

**Tipo de sistema:** Determinístico. Sem IA, sem modelos de linguagem, sem dependências externas além de `feedparser` (já presente na stack). Toda decisão é derivada de regras explícitas e pesos calibráveis.

**Principais responsabilidades:**

| Responsabilidade | Onde vive |
|---|---|
| Detectar categoria funcional do artigo | `news_classifier.py` |
| Detectar flags operacionais | `news_classifier.py` |
| Computar score de relevância | `news_classifier.py` |
| Derivar prioridade a partir do score | `news_classifier.py` |
| Buscar artigos via RSS | `rss_client.py` |
| Aplicar classificação a todos os artigos | `news_service.py` |
| Filtrar ruído | `news_service.py` |
| Deduplificar artigos repetidos entre feeds | `news_service.py` |
| Ordenar por relevância | `news_service.py` |
| Entregar payload para o briefing | `news_service.py` |

---

## 2. Linha do Tempo de Evolução

### V1 — Classificação Básica

**Estado anterior ao V1:** O `RSSClient` retornava artigos com 4 categorias simplistas (economia, tecnologia, negocios, geral) derivadas de keyword matching rudimentar. O `NewsService` passava todos os artigos sem filtro ao briefing, em ordem de fetch, sem score, sem flags e sem qualquer critério de qualidade. O `BriefingService` exibia os 3 primeiros itens da lista bruta — completamente arbitrários.

**O que foi implementado:**

- Criação de `app/integrations/news_classifier.py` como classificador centralizado, análogo ao `email_classifier.py` existente.
- 8 categorias funcionais: `macro`, `mercado`, `empresas`, `tecnologia`, `politica`, `internacional`, `setorial`, `ruido`.
- 7 flags operacionais por artigo: `has_market_impact`, `has_economic_impact`, `has_policy_impact`, `has_strong_signal`, `has_numbers`, `is_duplicate_candidate`, `is_noise_candidate`.
- Resultado tipado como `NewsClassification` (TypedDict) contendo `category` e `flags`.
- Detecção de ruído por lista de padrões e por título curto (< 3 palavras).
- Filtragem básica: artigos `ruido` excluídos de `items`, mantidos em `by_category` para auditoria.
- Fallback por exceção: qualquer falha individual retorna `category="setorial"`, todas as flags `False`.
- Delegação de classificação para fora do `rss_client.py`: o cliente passou a retornar `category=""` (parse only), com classificação acontecendo no `news_service.py`.

**Problemas resolvidos:**

- Categorias genéricas substituídas por taxonomia funcional e útil.
- Ruído visível filtrado antes de chegar ao briefing.
- Artigos enriquecidos com flags que descrevem seu potencial operacional.
- Contrato de `summarize_news()` preservado: mesmos 5 campos de retorno (`total`, `categories`, `by_category`, `items`, `summary`), com campos adicionais não-quebradores nos itens.

**Limitações que permaneceram após V1:**

- Sem score: todos os artigos válidos tinham o mesmo peso.
- Ordem dos itens ainda era ordem de fetch (arbitrária).
- Sem deduplicação: o mesmo artigo de múltiplos feeds aparecia múltiplas vezes.
- `has_numbers` ativado por qualquer dígito (incluindo números genéricos).

---

### V2 — Score e Priorização

**O que foi adicionado:**

- **Modelo de score determinístico** centralizado em `news_classifier.py`, com pesos explícitos por flag e por categoria.
- **Priority derivada de threshold:** `high` (≥ 6), `medium` (≥ 3), `low` (< 3).
- **`score_reasons`:** lista auditável com cada sinal que contribuiu para o score, com sinal e peso (`"+3 has_market_impact"`, `"-2 vague_title"`).
- **Penalidades por título vago** (−2) e **título curto < 4 palavras** (−1).
- **Deduplicação** via `_deduplicate_items()` em `news_service.py`: normalização de título (lowercase + remoção de pontuação), mantém o item de maior score por grupo, tie-break pelo primeiro visto. Executada antes da ordenação.
- **Ordenação única final:** `score DESC`, depois `published DESC` para desempate temporal. Artigos sem data ordenam por último.
- **Campos novos nos itens:** `score: int`, `priority: str`, `score_reasons: list[str]`.

**Como mudou o comportamento:**

Antes: `news["items"][:3]` no briefing mostrava os 3 primeiros artigos da ordem de chegada dos feeds — completamente arbitrários.

Depois: os 3 primeiros artigos são os de maior score e, em empate, os mais recentes. A chance de um artigo `high` aparecer no briefing é determinística e previsível.

**Ganhos reais:**

- O briefing passou a exibir os artigos mais relevantes, não os mais rápidos no fetch.
- Artigos duplicados (mesmo assunto em múltiplos feeds) foram eliminados, com o melhor exemplar mantido.
- A rastreabilidade de por que um artigo teve determinada prioridade tornou-se possível via `score_reasons`.

**Limitações que permaneceram após V2:**

- `has_numbers` ainda ativado por qualquer dígito (corrigido em V3).
- Datas com formatos inconsistentes comparadas como strings (risco de ordenação incorreta, corrigido em V3).
- Penalty de −2 aplicada ao item perdedor na deduplicação (desnecessário, limpo em V3).

---

### V3 — Refinamento e Estabilização

**Melhorias de precisão:**

- **`has_numbers` reescrito:** de `re.compile(r'\d')` (qualquer dígito) para `_ECONOMIC_NUMBER_RE` — regex que exige que o número esteja **adjacente** a um marcador econômico (`%`, `R$`, `$`, `bi`, `mi`, `tri`, `bilhões`, `milhões`, `trilhões`, `bps`, `pontos-base`). `"5 dicas para investir"` → `False`. `"R$ 3,5 bilhões"` → `True`.

- **`"desconto"` removido de `_NOISE`** (ajuste pós-audit): substituído por padrões compostos específicos (`"oferta com desconto"`, `"desconto imperdível"`) para evitar filtrar artigos legítimos de finanças contendo "taxa de desconto" ou "ações com desconto".

**Estabilização:**

- **Parsing de datas robusto:** `_parse_published()` com cascata ISO 8601 → RFC 2822 → `datetime.min`. Todos os datetimes normalizados para `timezone-naive` antes da comparação, eliminando risco de `TypeError` entre datas com e sem timezone.

- **Deduplicação limpa:** removida a penalidade de −2 sobre o item perdedor. O perdedor é marcado internamente com `is_duplicate_candidate=True` e descartado — sem modificação de score, sem efeito colateral.

- **Summary reformulado:** `"20 notícia(s) em 4 categoria(s). Destaques: 5 de alta prioridade."` — inclui contagem de HIGH quando positiva.

**Preparação para evolução futura:**

Cinco pontos `TODO: [V4]` inseridos nos locais de extensão natural:
- Detecção de tópicos tendência pós-dedup (clustering)
- Agrupamento temático dos itens ordenados
- Embedding similarity para artigos ambíguos que caem em `setorial`
- Score de credibilidade por fonte
- Geração de summary por IA substituindo a string atual

---

### V4 — Baseline Determinístico Avançado

**O que foi implementado:**

*Otimização do matching:* substituição de todas as iterações `any(t in text for t in frozenset)` por regex compilados com alternação única em `news_classifier.py`. 17 padrões compilados no carregamento do módulo. Custo por chamada reduzido de O(n×m) para O(m). Termos ordenados por comprimento decrescente para garantir que frases longas tenham precedência sobre substrings. `re.escape()` aplicado a todos os termos — incluindo os que contêm caracteres especiais como `"s.a."` e `"pré-mercado"`. Sem `\b` (word boundary) — matching substring, semanticamente equivalente ao original.

*Normalização centralizada:* criação de `_normalize_text(text: str) -> str` em `news_classifier.py`. Eliminou a duplicação de `_normalize_title()` + `_PUNCT_RE` + `_SPACE_RE` em `news_service.py`. Reutilização explícita: o texto normalizado é computado uma única vez no scope gate e passado como parâmetro para `_build_item()`, evitando recomputação.

*Scope gate híbrido (Modo 3):* criação de `app/integrations/tracked_scope.py`. Gate determinístico com três grupos compilados em regex: Grupo A (ativos monitorados), Grupo B (macro/política econômica), Grupo C (geopolítico/social com impacto material). Artigos descartados no gate **não chegam a `classify_news`**. Campo `_scope_gate_reason_internal` adicionado ao item para auditabilidade interna. Inserido como Layer 3 do pipeline, antes da classificação.

*SimHash v1 (near-duplicate gate):* ativação de `app/integrations/simhash_utils.py`. Threshold de 10 bits (conservador). Fingerprint 64-bit via bag-of-words (hashlib.md5). Reutiliza `_normalized_text` já presente no item — zero recomputação. First-seen heuristic: item anterior é mantido quando near-dup é detectado. Layer 7 do pipeline, após dedup exato e antes do ranking. O(n²) — aceitável para volume atual.

*Isolamento de campos internos:* items carregam campos `_`-prefixados durante o pipeline (`_normalized_text`, `_scope_gate_reason_internal`, `_simhash`, `_internal_score`, etc.). Todos removidos por `_strip_internal_fields()` antes da serialização na Layer 11. Contratos públicos e schemas Pydantic inalterados.

**Problemas resolvidos:**

- Custo de matching reduzido com padrões compilados em módulo-load.
- Notícias de empresas irrelevantes eliminadas antes da classificação.
- Near-duplicates com variação lexical (plural/singular, unidades diferentes) removidos do briefing.
- Texto normalizado reutilizado entre layers — zero redundância de computação.
- Campos de estado interno isolados com garantia de não-vazamento para APIs.

**Limitações que permanecem após V4:**

- SimHash com threshold=10 captura variações lexicais próximas (d≤10 bits), não paráfrases de vocabulário substancialmente diferente.
- Threshold não calibrado com dados reais — valor inicial conservador por design.
- `"vale"` (bare term) no Grupo A pode gerar falsos positivos ("vale transporte") em feeds não-financeiros.
- First-seen heuristic no SimHash não garante o item de maior score quando há near-duplicates.

---

## 3. Arquitetura do Módulo

### Visão de Componentes

```
app/integrations/
  rss_client.py          ← fetch + parse (sem classificação)
  news_classifier.py     ← classificação individual + normalização centralizada
  tracked_scope.py       ← scope gate: grupos A/B/C com regex compilado
  simhash_utils.py       ← fingerprint 64-bit para near-duplicate detection

app/modules/briefing/
  news_service.py        ← pipeline: 11 layers — filtra, classifica, deduplica, ordena
  service.py             ← BriefingService (consome summarize_news())
```

### Fluxo Completo RSS → Briefing

```
Feeds RSS configurados (settings.rss_default_feeds)
        │
        ▼
  RSSClient.fetch_all()
  • Busca até 10 artigos por feed
  • Parse via feedparser
  • Limpeza de HTML, extração de data (ISO format)
  • category="" (sem classificação nesta camada)
        │
        ▼ list[RSSArticle]
        │
  NewsService.summarize_news()
        │
        ├── Layer 1: Date gate
        │   └── _is_today_sp() → descarta artigos não publicados hoje (BRT)
        │
        ├── Layer 2: Quality gate
        │   └── is_low_quality() → descarta listicles, clickbait, títulos curtos
        │
        ├── Layer 3: Scope gate   [V4]
        │   └── _normalize_text() → normalized_text (computado uma única vez)
        │       evaluate_scope(normalized_text)
        │       ├── Grupo A: petrobras, vale3, ambev, ibovespa…
        │       ├── Grupo B: selic, copom, banco central, câmbio…
        │       └── Grupo C: guerra, sanções, conflito internacional…
        │       • DROP → scope_dropped_count++ (não chega a classify_news)
        │       • PASS → continua com normalized_text reutilizado
        │
        ├── Layer 4: Classification   [V4 — reutiliza normalized_text]
        │   └── _build_item(article, normalized_text)
        │       └── classify_news(title, summary, source)
        │           ├── _detect_news_flags()          → NewsFlags (regex compilado)
        │           ├── _infer_news_category()        → str (regex compilado)
        │           ├── _score_news()                 → tuple[int, list[str]]
        │           └── _derive_priority_from_score() → str
        │       • item enriquecido com campos públicos + _-prefixados internos
        │
        ├── Layer 5: Noise split
        │   ├── noise_items → by_category["ruido"] (auditoria)
        │   └── valid_items → continua no pipeline
        │
        ├── Layer 6: Exact dedup
        │   └── _deduplicate_items()
        │       • _normalize_text(item["title"]) como chave
        │       • mantém maior score por grupo; tie-break: primeiro visto
        │
        ├── Layer 7: Near-duplicate gate (SimHash)   [V4]
        │   └── _filter_near_duplicates()
        │       • simhash(item["_normalized_text"]) → fingerprint 64-bit
        │       • hamming_distance(h, existing) ≤ 10 → near-dup → descartar
        │       • PASS → _simhash adicionado ao item (campo interno)
        │
        ├── Layer 8: Ranking
        │   └── _rank_items()
        │       • final_score = score + quality_score*2
        │       • sort: final_score DESC → published DESC
        │
        ├── Layer 9: Curation
        │   └── _curate_top5() → max 3 high + medium, low descartado
        │
        ├── Layer 10: Diversity
        │   └── _diversify() → cap same-category ≤ 2 quando alternativa existe
        │
        └── Layer 11: Output
            └── _strip_internal_fields() → remove todos os _-prefixados
                ├── by_category (curated + noise, sem campos internos)
                ├── items (curated limpos)
                └── summary (Telegram-aware one-liner)
                        │
                        ▼
              BriefingService._compose()
              • consome news["summary"]
              • consome news["items"] → title, category, priority
```

---

## 4. Pipeline — Descrição Passo a Passo

**Step 1 — Classificar e pontuar cada artigo**

Para cada `RSSArticle` retornado pelo cliente:
1. Texto de análise: `f"{title} {summary}".lower()`
2. `_detect_news_flags()` detecta 7 flags via keyword matching
3. `_infer_news_category()` atribui categoria por ordem de prioridade; se `is_noise_candidate=True`, retorna `"ruido"` imediatamente
4. `_score_news()` computa score somando pesos de flags + bônus de categoria + penalidades de título
5. `_derive_priority_from_score()` deriva `high/medium/low` pelos thresholds
6. Item é enriquecido: campos originais de `RSSArticle` + `category`, `flags`, `score`, `priority`, `score_reasons`

Fallback por exceção: `classify_news()` envolve toda a lógica em `try/except`. Qualquer erro retorna `category="setorial"`, `score=0`, `priority="low"`, `score_reasons=["fallback"]`.

**Step 2 — Separar ruído**

Artigos com `category="ruido"` são separados do pipeline principal:
- Mantidos em `noise_items` para posterior inclusão em `by_category["ruido"]` (auditoria)
- Não participam de deduplicação nem ordenação
- Não aparecem em `items` no payload final

**Step 3 — Deduplificar**

`_deduplicate_items(valid_items)` opera sobre os artigos válidos em ordem de fetch:
1. Título normalizado: lowercase + remoção de pontuação + colapso de espaços
2. Primeira ocorrência de cada título normalizado → adicionada ao resultado
3. Ocorrência posterior com mesmo título normalizado:
   - Score maior → substitui o anterior na mesma posição
   - Score igual ou menor → descartada (primeiro visto mantido)
4. Item descartado recebe `is_duplicate_candidate=True` internamente
5. Score do vencedor **nunca é modificado**

**Step 4 — Ordenação única final**

```python
sorted(deduped, key=lambda i: (i["score"], _parse_published(i.get("published") or "")), reverse=True)
```

- Chave primária: `score` (decrescente)
- Chave secundária: `datetime` (decrescente — mais recente primeiro)
- Artigos sem data ou com data inválida: recebem `datetime.min` e ordenam por último no grupo de mesmo score
- Ordenação estável: itens com mesmo score e mesma data mantêm ordem relativa pré-sort
- **Executada uma única vez, ao final do pipeline**

**Step 5 — Montar resultado**

Recalcula `by_category` a partir dos itens finais ordenados + adiciona `noise_items` em `by_category["ruido"]`. Computa `categories` excluindo ruído. Conta `high_count`. Monta o payload com shape contratado.

---

## 5. Modelo de Decisão

### Categorias e Ordem de Prioridade

A categoria de um artigo é determinada pela **primeira correspondência** na sequência abaixo. A ordem reflete especificidade decrescente:

| Posição | Categoria | Exemplos de keywords |
|---|---|---|
| 1 | `macro` | pib, selic, ipca, câmbio, banco central, fed, fmi |
| 2 | `mercado` | ibovespa, b3, ações, commodities, tesouro direto, spread |
| 3 | `politica` | governo, senado, decreto, stf, reforma tributária, lula |
| 4 | `internacional` | eua, china, trump, g20, guerra, tarifas comerciais |
| 5 | `empresas` | aquisição, fusão, resultado trimestral, ceo, layoff |
| 6 | `tecnologia` | inteligência artificial, openai, big tech, semicondutor |
| 7 | `setorial` | agronegócio, infraestrutura, saúde pública, varejo |
| — | `ruido` | short-circuit se `is_noise_candidate=True` |

### Flags Operacionais

| Flag | Ativado quando | Peso no score |
|---|---|---|
| `has_market_impact` | termos de mercado financeiro (ibovespa, câmbio, selic…) | +3 |
| `has_economic_impact` | indicadores macro (pib, inflação, recessão, déficit…) | +3 |
| `has_policy_impact` | eventos regulatórios (decreto, aprovado, vetado, norma…) | +2 |
| `has_strong_signal` | eventos de alta magnitude (crise, colapso, default…) | +2 |
| `has_numbers` | número **adjacente** a marcador econômico (%, R$, bi, bps…) | +1 |
| `is_noise_candidate` | padrão de ruído OU título < 3 palavras | −3 |
| `is_duplicate_candidate` | artigo identificado como duplicata na deduplicação | (sem peso no score) |

### Bônus por Categoria

| Categoria | Bônus |
|---|---|
| macro, mercado | +2 |
| politica, internacional, empresas, tecnologia | +1 |
| setorial | 0 |
| ruido | −3 (irrelevante — artigo filtrado antes de chegar ao score) |

### Penalidades por Qualidade de Título

| Condição | Penalidade |
|---|---|
| Título presente em `_VAGUE_TITLE` (destaques, resumo do dia, manchetes…) | −2 |
| Título com < 4 palavras | −1 |

### Thresholds de Prioridade

```
score ≥ 6  →  "high"
score ≥ 3  →  "medium"
score < 3  →  "low"
```

Score teórico máximo (todos os sinais positivos, sem penalidades): **13**
Score teórico mínimo: **−6**
Intervalo prático de `high` observado: **6–11**

### Exemplo de Cálculo Completo

**Artigo:** "Selic sobe para 13,75% ao ano em decisão histórica do Copom"

```
has_market_impact  (selic)              → +3
has_economic_impact                     →  0  (selic não está em _ECONOMIC_IMPACT)
has_policy_impact                       →  0
has_strong_signal  (decisão histórica)  → +2
has_numbers        (13,75%)             → +1
is_noise_candidate                      →  0

categoria: macro                        → +2
título: 11 palavras, não vago           →  0

score total: 8  →  priority: "high"
score_reasons: ["+3 has_market_impact", "+2 has_strong_signal", "+1 has_numbers", "+2 category_macro"]
```

### Detecção de `has_numbers`

A flag **não** é ativada por qualquer dígito. Exige número **adjacente** a um dos marcadores econômicos abaixo:

```
%           → "lucro sobe 15%"
R$          → "R$ 3,5 bilhões"
$           → "$ 50 milhões"
bi, mi, tri → "captou R$ 5 bi"
bilhões, milhões, trilhões
bps         → "50 bps de alta"
pontos-base → "25 pontos-base"
```

### Deduplicação

1. Título normalizado: `lowercase` + remoção de pontuação + colapso de espaços
2. `"Ibovespa cai 2%!"` e `"Ibovespa cai 2%"` → `"ibovespa cai 2"` (mesma chave)
3. Para cada chave duplicada: mantém o item com maior `score`; empate → mantém o primeiro visto
4. Perdedor: marcado com `is_duplicate_candidate=True` e descartado do output
5. Score do vencedor: nunca modificado
6. Limitação: detecta apenas títulos idênticos pós-normalização; artigos sobre o mesmo evento com títulos diferentes **não** são deduplificados

---

## 6. Contratos e Garantias

### Estrutura de Retorno de `summarize_news()`

```python
{
    "total"      : int,       # count de itens válidos (pós-filtro e pós-dedup)
    "categories" : dict,      # {str: int} — {categoria: count}, excluindo "ruido"
    "by_category": dict,      # {str: list[dict]} — todos os artigos agrupados, incluindo "ruido"
    "items"      : list[dict],# artigos válidos, ordenados por (score DESC, published DESC)
    "summary"    : str,       # "N notícia(s) em M categoria(s)[. Destaques: X de alta prioridade.]"
}
```

### Campos Garantidos em Cada Item

**Campos originais do `RSSArticle` (nunca removidos):**

```python
"title"     : str   # título do artigo
"link"      : str   # URL de origem
"source"    : str   # título do feed
"published" : str   # ISO 8601 ou string raw do feed; pode ser ""
"summary"   : str   # texto do artigo (HTML limpo)
"category"  : str   # categoria classificada (antes era "")
```

**Campos adicionados pelo pipeline (aditivos, não-quebradores):**

```python
"flags"         : dict       # 7 campos booleanos (NewsFlags)
"score"         : int        # score de relevância
"priority"      : str        # "high" | "medium" | "low"
"score_reasons" : list[str]  # ex: ["+3 has_market_impact", "+2 category_macro"]
```

### Compatibilidade com BriefingService

O `BriefingService._compose()` consome exatamente:

```python
news["summary"]              # string → garantido
news.get("items", [])[:3]   # lista fatiável → garantido
item["title"]                # string presente em todo item → garantido
```

Nenhum campo existente foi removido. Nenhum campo novo é obrigatório para o `BriefingService`.

### Garantias de Não Regressão

- `BriefingService` não foi modificado em nenhuma das três fases.
- O shape de `summarize_news()` não foi alterado — apenas os valores melhoraram.
- Falha em um artigo individual (`classify_news()` lança exceção) → fallback aplicado, processamento continua.
- Falha em um feed RSS → `RSSClient` captura por feed, continua os demais.
- Feed vazio ou todos os feeds indisponíveis → `total=0`, `items=[]`, `summary="0 notícia(s) em 0 categoria(s)."`. `BriefingService` renderiza sem erro.

---

## 7. Responsabilidades dos Arquivos

### `app/integrations/news_classifier.py`

**Responsabilidade única:** classificar um artigo individual + centralizar a normalização de texto. Não conhece listas, não faz I/O, não mantém estado.

| Componente | Tipo | Função |
|---|---|---|
| `NewsFlags` | TypedDict | Estrutura dos 7 flags operacionais |
| `NewsClassification` | TypedDict | Estrutura de saída: category, flags, score, priority, score_reasons |
| `_MACRO` … `_SETORIAL` | `frozenset[str]` | Keywords por categoria (vocabulário de referência) |
| `_MACRO_RE` … `_SETORIAL_RE` | `re.Pattern` | Regex compilado por categoria (single-pass matching) |
| `_MARKET_IMPACT_RE` … `_NOISE_RE` | `re.Pattern` | Regex compilado por flag operacional |
| `_ECONOMIC_NUMBER_RE` | `re.Pattern` | Regex: número adjacente a marcador econômico |
| `_CATEGORY_PATTERNS` | `list[tuple]` | Pares (categoria, padrão compilado) — ordem preservada |
| `SCORE_WEIGHTS` | `dict[str, int]` | Pesos por flag (fonte única de calibração) |
| `CATEGORY_SCORE` | `dict[str, int]` | Bônus/penalidade por categoria |
| `SCORE_THRESHOLD_HIGH/MEDIUM` | `int` | Limiares de prioridade |
| `_normalize_text()` | função pública | Normalização compartilhada: lowercase + strip punctuation + collapse spaces |
| `_build_pattern()` | função privada | Compila frozenset em regex de alternação ordenada por comprimento |
| `classify_news()` | função pública | API com try/except e fallback explícito |
| `compute_quality_score()` | função pública | Modificador de ranking 0–2 (não afeta prioridade) |
| `is_low_quality()` | função pública | Gate pré-score: listicle, clickbait, reciclado |
| `_infer_news_category()` | função privada | Categoria por regex compilado + short-circuit de ruído |
| `_detect_news_flags()` | função privada | 7 flags via regex compilado (single-pass each) |
| `_score_news()` | função privada | Score composto + score_reasons auditável |
| `_derive_priority_from_score()` | função privada | `high / medium / low` via threshold |

---

### `app/integrations/tracked_scope.py`

**Responsabilidade única:** determinar se um artigo está no escopo do pipeline (Modo 3: portfolio\_macro\_geo). Não classifica, não pontua, não faz I/O.

| Componente | Tipo | Função |
|---|---|---|
| `_GROUP_A_TERMS` | `list[str]` | Ativos monitorados: Petrobras, Vale, Ambev, Itaúsa, Ibovespa |
| `_GROUP_B_TERMS` | `list[str]` | Macro/política econômica: Selic, Copom, câmbio, dólar… |
| `_GROUP_C_TERMS` | `list[str]` | Geopolítico/social com impacto material: guerra, sanções… |
| `_GROUP_A_RE` / `_GROUP_B_RE` / `_GROUP_C_RE` | `re.Pattern` | Padrões compilados, termos ordenados por comprimento decrescente |
| `_build_scope_pattern()` | função privada | Compila lista de termos em regex de alternação |
| `evaluate_scope()` | função pública | `(bool, str \| None)` — grupo ativado ou `(False, None)` |

**Contrato de normalização:** o caller é responsável por normalizar o texto via `_normalize_text` antes de chamar `evaluate_scope`. O módulo não re-normaliza.

---

### `app/integrations/simhash_utils.py`

**Responsabilidade única:** utilitários de fingerprint para near-duplicate detection. Sem estado, sem I/O, sem dependências externas.

| Componente | Tipo | Função |
|---|---|---|
| `simhash(text, bits=64)` | função pública | Fingerprint inteiro de `bits` bits via bag-of-words + MD5 |
| `hamming_distance(h1, h2)` | função pública | Número de bits diferentes entre dois fingerprints |

**Algoritmo:** para cada token (whitespace split + lowercase), computa MD5 como inteiro; acumula vetor de votos (+1/−1) por bit; colapsa: bit i = 1 se v[i] > 0. Propriedade: distância de Hamming ≈ distância de cosseno entre bag-of-words.

---

### `app/modules/briefing/news_service.py`

**Responsabilidade:** orquestrar o pipeline de 11 layers. Não conhece regras de classificação ou scope — delega completamente aos módulos de integração.

| Componente | Tipo | Função |
|---|---|---|
| `_parse_published()` | função módulo | Parser ISO/RFC2822 com fallback `datetime.min` |
| `_is_today_sp()` | função módulo | Date gate: artigo publicado hoje em BRT? |
| `_strip_internal_fields()` | função módulo | Remove todos os campos `_`-prefixados antes da serialização |
| `_build_item()` | função módulo | Classifica artigo e constrói dict enriquecido (públicos + internos) |
| `_curate_top5()` | função módulo | Seleciona top-5: max 3 high + medium; low descartado |
| `_deduplicate_items()` | função módulo | Dedup exato por título normalizado; mantém maior score |
| `_filter_near_duplicates()` | função módulo | SimHash gate: first-seen heuristic com threshold de Hamming |
| `_SIMHASH_THRESHOLD` | constante | 10 bits — valor conservador inicial, calibrável |
| `_rank_items()` | função módulo | Sort por final\_score = score + quality\_score\*2, depois published DESC |
| `_diversify()` | função módulo | Cap same-category ≤ 2 quando alternativa de igual ou maior prioridade existe |
| `_infer_focus()` | função módulo | Top-2 labels de categoria para o summary do Telegram |
| `NewsService.summarize_news()` | método | Pipeline completo em 11 layers explícitos |
| `NewsService.normalize_articles()` | método | Artigos classificados sem gate, sem filtro, sem ordenação |
| `NewsService.fetch_rss()` | método | Artigos brutos sem classificação (raw) |
| `NewsService.get_briefing()` | método | Alias de compatibilidade para `summarize_news()` |

---

### `app/integrations/rss_client.py`

**Responsabilidade:** fetch + parse. Não classifica. Não conhece categorias ou scores.

- `RSSArticle`: dataclass com campos `title`, `link`, `source`, `category` (sempre `""`), `published`, `summary`
- `RSSClient.fetch_all()`: busca até 10 artigos por feed, parse via feedparser, limpeza de HTML, extração de data para ISO
- `RSSClient._clean_html()`: remove tags HTML, faz unescape de entidades
- `RSSClient._extract_published()`: converte RFC 2822 para ISO via `parsedate_to_datetime`
- `RSSClient.to_dict()`: serializa `RSSArticle` para `dict`

### Separação de Responsabilidades

O modelo segue separação limpa entre o que classificar (classifier), como processar a lista (service) e como fazer fetch (client):

- O classifier não sabe que existe uma lista de artigos — processa um por vez.
- O service não sabe como classificar — delega completamente ao classifier.
- O `RSSClient` não sabe que existe classificação — apenas fetcha e parseia.
- O `BriefingService` não sabe o que são categorias ou scores — apenas consome o payload.

---

## 8. Limitações Conhecidas

### Heurística de Classificação

- A categoria é determinada pela **primeira correspondência** na lista de prioridade. Um artigo sobre "reforma tributária que afeta o Ibovespa" seria classificado como `macro` (porque termos macro têm prioridade sobre `mercado`), potencialmente perdendo a nuance de impacto em mercado.
- Artigos em inglês ou com termos técnicos não cobertos pelos sets de keywords caem em `setorial` por padrão, sem sinalização explícita de baixa confiança.
- O sistema não distingue intensidade: "Ibovespa cai 0,1%" e "Ibovespa despenca 8%" têm o mesmo `has_market_impact`.
- Não há distinção entre fontes: um feed de baixa qualidade e um feed do Banco Central têm o mesmo peso.
- Termos como `"crescimento"` em `_ECONOMIC_IMPACT` e `"governo"` em `_POLITICA` são suficientemente genéricos para aparecer em contextos não econômicos.

### Deduplicação Exata

- Detecta apenas títulos **idênticos após normalização**. Artigos sobre o mesmo evento com títulos diferentes ("Fed mantém juros" e "Banco central americano não altera taxa") não são identificados como duplicatas pelo dedup exato.
- Títulos muito curtos (2–3 palavras após normalização) aumentam o risco de falsos positivos.

### SimHash (Near-Duplicate Gate)

- O SimHash é bag-of-words: captura variações lexicais próximas (mesmo vocabulário com pequenas diferenças) mas **não** captura paráfrases semânticas com vocabulário substancialmente diferente.
- Threshold de 10 bits conservador por design: paráfrases como "Selic sobe 0,5 ponto, diz BC" (d=23 em relação a "Banco Central eleva Selic em 0,5 ponto") não são removidas. Threshold precisará de calibração com dados reais.
- First-seen heuristic: quando near-duplicates são detectados, o item mais antigo na ordem de chegada é mantido, independente do score. O ranking posterior reordena por qualidade, mitigando o impacto.
- Complexidade O(n²) na comparação de hashes — aceitável para volume atual (< 200 itens/dia após gates upstream). Monitorar se volume crescer acima de ~1.000 itens/sessão.

### Scope Gate

- `"vale"` (bare term) no Grupo A pode gerar falsos positivos em feeds não-financeiros ("vale transporte", "vale alimentação"). Aceito porque os feeds do Atlas são fontes financeiras. Mitigation futura: usar `"vale3"` como único match não-ambíguo ou adicionar negative lookahead.
- `"guerra"` e `"greve"` são termos amplos: "guerra de preços" ou "greve de professores" (sem impacto de mercado) passariam no gate. Trade-off intencional: falsos negativos (drops indevidos de notícias relevantes) são mais custosos que falsos positivos no briefing de mercado.

### Score

- Os pesos foram definidos por julgamento, não por calibração com dados reais. A distribuição de `high/medium/low` nos primeiros dias pode requerer ajuste.
- Não há decay temporal: um artigo de ontem com score 9 e um de hoje com score 9 são equivalentes — a data só desempata, não penaliza a antiguidade.
- Score máximo teórico atingível (13) não é esperado em artigos reais.

### Labels de Prioridade

- O módulo News usa `"high/medium/low"` (EN) enquanto o módulo Email usa `"alta/media/baixa"` (PT-BR). Qualquer código que compare prioridades entre os dois módulos precisará de mapeamento explícito.

### Fora do Escopo desta Fase

- IA / LLM — nenhuma integração implementada.
- Módulo de email — não faz parte desta fase.
- Thread dedup — não implementado.
- Rule engine global — não implementado.
- LSH / MinHash / banding — não implementados (SimHash v1 é suficiente para volume atual).

---

## 9. Decisões Arquiteturais

**1. Sistema determinístico sem IA**
Decisão deliberada para Fase 1 do Atlas. O comportamento é previsível, depurável e não requer infraestrutura adicional. A mesma entrada sempre produz a mesma saída. Pontos de extensão para IA estão identificados com `TODO: [V4]` mas não implementados.

**2. Módulo de notícias permanece dentro do contexto do briefing**
Não foi criado `app/modules/news/`. As notícias existem apenas para compor o briefing nesta fase. A extração para módulo próprio está reservada para quando o caso de uso de notícias independentes for necessário.

**3. Classificador como arquivo separado do service**
Seguindo o padrão estabelecido pelo `email_classifier.py`, o `news_classifier.py` foi isolado em `app/integrations/`, com responsabilidade única de classificar um artigo individual. O service orquestra; o classifier decide.

**4. TypedDict como tipo de retorno do classifier**
Preferido sobre `@dataclass` porque é compatível com `dict` existente no payload, sem overhead de conversão. Mantém integração direta com `{**RSSClient.to_dict(a), "category": ..., "flags": ...}`.

**5. Ausência de dependências externas**
`re`, `datetime`, `email.utils` são stdlib Python. `feedparser` já existia na stack. Nenhum pacote novo foi adicionado nos módulos de classificação.

**6. Contrato de `summarize_news()` preservado integralmente durante todo o ciclo V1–V3**
Os 5 campos originais foram mantidos com os mesmos tipos. Campos novos foram adicionados apenas dentro dos itens. O `BriefingService` continuou funcionando sem modificação em nenhuma das três fases.

**7. Fallback explícito e tipado**
Exceções em classificação individual resultam em `category="setorial"`, `score=0`, `priority="low"`, `score_reasons=["fallback"]` — nunca em crash ou dado ausente. O fallback é um dado válido, não um estado de erro silencioso.

**8. Ordenação única ao final do pipeline**
A ordenação acontece uma única vez, após deduplicação, sobre os itens já classificados e filtrados. Não há ordenações intermediárias. A chave de ordenação `(score, datetime)` é determinística e estável.

---

## 10. Pontos de Extensão Futura (V4)

Os cinco pontos de extensão estão marcados com `TODO: [V4]` no código nos locais exatos de injeção:

**1. Embedding similarity para artigos ambíguos**
- Localização: `news_classifier.py → _infer_news_category()`
- Artigos que não ativam nenhuma keyword e caem em `setorial` por padrão poderiam ser reclassificados por similaridade semântica com embeddings pré-computados por categoria.

**2. Score de credibilidade por fonte**
- Localização: `news_classifier.py → _score_news()`
- Um registro de fontes confiáveis (Banco Central, CVM, Reuters, Valor Econômico) poderia adicionar bônus de score; fontes de baixa qualidade conhecidas receberiam penalidade.

**3. Detecção de tópicos tendência**
- Localização: `news_service.py`, após Step 3 (deduplicação)
- Após deduplicação, múltiplos artigos sobre o mesmo evento (com títulos diferentes) poderiam ser agrupados por similaridade semântica, sinalizando que um tema é tendência.

**4. Agrupamento temático dos itens ordenados**
- Localização: `news_service.py`, após Step 4 (ordenação)
- Os itens poderiam ser devolvidos em grupos temáticos em vez de lista plana, enriquecendo a estrutura do briefing.

**5. Summary gerado por IA**
- Localização: `news_service.py → result["summary"]`
- O campo `"summary"` é o ponto de substituição natural por um digest gerado por LLM com base nos top-N artigos classificados.

---

## 11. Critérios de Sucesso

### O que significa "funcionando bem"

- Os 3 artigos no topo do briefing são os de maior relevância observável no dia — não artigos randômicos ou promocionais.
- Artigos repetidos entre feeds aparecem uma única vez.
- `by_category["ruido"]` contém apenas artigos genuinamente ruidosos (clickbait, promoção, sem conteúdo informacional).
- `score_reasons` dos artigos `high` contêm pelo menos 2 sinais positivos coerentes com o conteúdo.

### O que observar no uso real (primeiros dias)

| Sinal observado | Interpretação |
|---|---|
| 3–8 artigos HIGH em batch de 30–50 | Normal — calibração adequada |
| 0 artigos HIGH em todos os dias | Score muito conservador — revisar thresholds |
| > 15 artigos HIGH | Score muito permissivo — revisar pesos |
| `by_category["ruido"]` com artigos de Tesouro Direto ou valuation | Falso positivo em `_NOISE` — ajuste cirúrgico necessário |
| Artigo importante ausente do briefing | Verificar se caiu em ruído por substring inesperada |
| Duplicatas visíveis no briefing | `_normalize_title()` não capturou a variação — investigar título |

### Sinais de que o sistema está saudável

- Logs de `summarize_news` mostram `high > 0` na maioria dos dias úteis.
- `total` pós-dedup e pós-filtro é consistentemente menor que o raw do fetch (ruídos e duplicatas sendo removidos).
- `score_reasons` em artigos `high` são semanticamente coerentes com o tema.

---

## 12. Estado Atual

| Dimensão | Avaliação |
|---|---|
| **Ciclo** | V4 — Baseline Determinístico Avançado |
| **Maturidade** | Médio-alto — funcional, não calibrado |
| **Pronto para uso real** | **Sim** |
| **Nível de risco operacional** | Baixo |
| **Calibração de produção** | Pendente — requer uso real |

**Justificativa:**

O sistema é funcionalmente correto, determinístico e resiliente. Pipeline de 11 layers com responsabilidades isoladas. Contratos públicos e schemas Pydantic inalterados ao longo de todo o ciclo V1–V4. O `BriefingService` continua funcionando sem qualquer modificação. Audits técnicos executados em cada fase — nenhuma regressão detectada.

A maturidade é "médio-alto" e não "alto" por três razões deliberadas: (1) os pesos e thresholds do classificador foram definidos por julgamento, não por observação de dados reais; (2) o threshold do SimHash (10 bits) é conservador e não calibrado; (3) o scope gate pode precisar de ajuste fino nos termos do Grupo A ("vale") após validação com feeds reais.

O risco operacional é baixo: todos os casos de erro têm fallback explícito, o pior cenário de falha (feed RSS indisponível, artigo com encoding incomum) está coberto, e o SimHash gate opera de forma stateless — falha em um fingerprint não afeta os demais.

**Esta fase está consolidada.** Ajustes futuros dependem de uso real e coleta de evidências. O módulo de email não faz parte desta fase.

**Próximos passos recomendados:**

1. Uso real controlado — observar `scope_dropped`, `simhash_dropped` e `curated` nos logs de `summarize_news`.
2. Calibração do threshold SimHash — se near-duplicates semânticos chegam ao briefing, elevar threshold de 10 para ~14–18 e medir impacto em falsos positivos.
3. Refinamento do Grupo A — avaliar se "vale" (bare term) gera falsos positivos observáveis; substituir por "vale3" + "vale s.a." se necessário.
4. Calibração de scores — ajustar pesos com base na distribuição real de `high/medium/low` observada.
