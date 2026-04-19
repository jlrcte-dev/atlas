# Módulo News / RSS — Atlas AI Assistant

> Documentação técnica oficial. Ciclo V1–V3 concluído. Última atualização: Abril 2026.

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

## 3. Arquitetura do Módulo

### Visão de Componentes

```
app/integrations/
  rss_client.py          ← fetch + parse (sem classificação)
  news_classifier.py     ← classificação individual por artigo

app/modules/briefing/
  news_service.py        ← pipeline: classifica, filtra, deduplica, ordena
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
        ├── Step 1: classificar + pontuar cada artigo
        │   └── classify_news(title, summary, source)
        │       ├── _detect_news_flags()          → NewsFlags
        │       ├── _infer_news_category()        → str
        │       ├── _score_news()                 → tuple[int, list[str]]
        │       └── _derive_priority_from_score() → str
        │
        ├── Step 2: separar ruído
        │   ├── noise_items → by_category["ruido"] (auditoria)
        │   └── valid_items → continua no pipeline
        │
        ├── Step 3: deduplificar (antes do sort)
        │   └── _deduplicate_items()
        │       • normalized title matching
        │       • mantém maior score por grupo
        │       • tie-break: primeiro visto
        │
        ├── Step 4: ordenação única final
        │   └── sorted(key=(score DESC, published DESC))
        │       • _parse_published() com fallback para datetime.min
        │
        └── Step 5: montar resultado
            ├── total, categories, by_category
            ├── items (ordenados, sem ruído, sem duplicatas)
            └── summary (string com contagem + HIGH count)
                    │
                    ▼
          BriefingService._compose()
          • consome news["summary"]
          • consome news["items"][:3]  →  apenas item["title"]
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

**Responsabilidade única:** classificar um artigo individual. Não conhece listas, não faz I/O, não mantém estado. Entrada: `(title, summary, source)`. Saída: `NewsClassification`.

| Componente | Tipo | Função |
|---|---|---|
| `NewsFlags` | TypedDict | Estrutura dos 7 flags operacionais |
| `NewsClassification` | TypedDict | Estrutura de saída: category, flags, score, priority, score_reasons |
| `_MACRO` … `_SETORIAL` | `frozenset[str]` | Keywords por categoria (imutáveis) |
| `_MARKET_IMPACT` … `_STRONG_SIGNAL` | `frozenset[str]` | Keywords por flag (imutáveis) |
| `_NOISE` | `frozenset[str]` | Padrões de ruído (após ajuste pós-audit) |
| `_VAGUE_TITLE` | `frozenset[str]` | Padrões de título vago (penalidade −2) |
| `_ECONOMIC_NUMBER_RE` | `re.Pattern` | Regex: número adjacente a marcador econômico |
| `_CATEGORY_PRIORITY` | `list[tuple]` | Ordem de prioridade entre categorias |
| `SCORE_WEIGHTS` | `dict[str, int]` | Pesos por flag (fonte única de calibração) |
| `CATEGORY_SCORE` | `dict[str, int]` | Bônus/penalidade por categoria |
| `SCORE_THRESHOLD_HIGH/MEDIUM` | `int` | Limiares de prioridade |
| `classify_news()` | função pública | API com try/except e fallback explícito |
| `_infer_news_category()` | função privada | Categoria por prioridade + short-circuit de ruído |
| `_detect_news_flags()` | função privada | 7 flags por keyword matching |
| `_score_news()` | função privada | Score composto + score_reasons auditável |
| `_derive_priority_from_score()` | função privada | `high / medium / low` via threshold |

---

### `app/modules/briefing/news_service.py`

**Responsabilidade:** orquestrar o pipeline de artigos. Não conhece regras de classificação — delega completamente ao classifier.

| Componente | Tipo | Função |
|---|---|---|
| `_parse_published()` | função módulo | Parser ISO/RFC2822 com fallback `datetime.min` |
| `_normalize_title()` | função módulo | Normalização para deduplicação |
| `_deduplicate_items()` | função módulo | Deduplicação por título normalizado |
| `NewsService.summarize_news()` | método | Pipeline completo em 5 steps explícitos |
| `NewsService.normalize_articles()` | método | Artigos classificados sem filtro/ordenação |
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

### Deduplicação

- Detecta apenas títulos **idênticos após normalização**. Artigos sobre o mesmo evento com títulos diferentes ("Fed mantém juros" e "Banco central americano não altera taxa") não são identificados como duplicatas.
- Títulos muito curtos (2–3 palavras após normalização) aumentam o risco de falsos positivos.

### Score

- Os pesos foram definidos por julgamento, não por calibração com dados reais. A distribuição de `high/medium/low` nos primeiros dias pode requerer ajuste.
- Não há decay temporal: um artigo de ontem com score 9 e um de hoje com score 9 são equivalentes — a data só desempata, não penaliza a antiguidade.
- Score máximo teórico atingível (13) não é esperado em artigos reais.
- `"crescimento"` como flag de `has_economic_impact` é amplo: aparece em contextos de tech, startups e empresas mesmo quando não há impacto macro real.

### Labels de Prioridade

- O módulo News usa `"high/medium/low"` (EN) enquanto o módulo Email usa `"alta/media/baixa"` (PT-BR). Qualquer código que compare prioridades entre os dois módulos precisará de mapeamento explícito.

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
| **Maturidade** | Médio-alto |
| **Pronto para uso real** | **Sim** |
| **Nível de risco operacional** | Baixo |

**Justificativa:**

O sistema é funcionalmente correto, determinístico e resiliente. Todos os casos de erro têm fallback explícito. O contrato com o `BriefingService` é estável. O audit pré-produção foi executado (Abril 2026) e o único ajuste blocker (`"desconto"` em `_NOISE`) foi aplicado.

A maturidade é "médio-alto" e não "alto" porque os pesos e thresholds foram definidos por julgamento, não por observação de dados reais. A calibração fina pertence à próxima iteração após coleta de comportamento em produção.

O risco operacional é baixo: o pior cenário de falha (feed RSS indisponível, artigo com encoding incomum) está coberto pelos fallbacks existentes. Não há risco de crash do briefing por falha no módulo de notícias.
