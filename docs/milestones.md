# Atlas AI Assistant — Milestones do Projeto

> Documento de referência estratégica. Última atualização: Abril 2026.

---

## 1. Visão Geral

O **Atlas** é um sistema de inteligência operacional pessoal que centraliza dados dispersos (email, calendário, notícias) e os transforma em informação acionável, entregue diariamente via briefing consolidado.

O Atlas não é um chat genérico. É um hub de automação orientado à tomada de decisão:

- **Organização de dados** — classifica, prioriza e filtra informação relevante
- **Integração com ferramentas externas** — Google Calendar, Gmail, Outlook, feeds RSS
- **Automação de tarefas** — geração de briefing diário, identificação de ação requerida
- **Apoio à decisão** — destaca o que importa, reduz o que polui

**Abordagem atual (Fase 1):** Determinística. Sem IA, sem LLM, sem dependências externas além da stack definida. Todo comportamento é derivado de regras explícitas, pesos calibráveis e heurísticas de keyword matching. A mesma entrada sempre produz a mesma saída.

**Stack:** Python 3.11+, FastAPI, SQLite, Google APIs, feedparser.

---

## 2. Evolução dos Módulos

### Inbox / Email

**Estado inicial:** Listagem simples de emails sem nenhum critério de relevância. Todos os emails tratados igualmente, sem classificação, sem prioridade, sem identificação de ação requerida.

**Evolução implementada:**

O módulo Inbox passou por duas gerações de evolução, implementadas em `app/integrations/email_classifier.py` e `app/modules/inbox/service.py`:

**Geração 1 — Classificação por categoria:**
- Introdução de 4 categorias funcionais: `action`, `update`, `newsletter`, `noise`
- Precedência de classificação: `newsletter` → `noise` → `action` → `update`
- Newsletter e noise com short-circuit absoluto (sem score, prioridade = baixa imediatamente)
- Flags operacionais por email: `requires_response`, `has_deadline`, `is_follow_up`, `is_opportunity`

**Geração 2 — Score contextual e priorização:**
- Modelo de score determinístico com pesos por flag e heurística de remetente
- Pesos: `has_deadline (+4)`, `requires_response (+4)`, `is_opportunity (+2)`, `is_follow_up (+2)`, `human_sender (+2)`, `bulk_sender (−3)`
- Thresholds: `alta` (≥ 4), `media` (≥ 0), `baixa` (< 0)
- `score_reasons` auditável por email
- `action_items`: emails com qualquer flag operacional, ordenados por score
- Fallback por exceção individual: nunca aborta o processamento do inbox

**Capacidades atuais:**

- Classificação automática de todos os emails em 4 categorias
- Priorização por score: `alta / media / baixa`
- Identificação de emails que exigem ação (`requires_response`, `has_deadline`)
- Identificação de follow-ups e oportunidades comerciais
- Filtragem de newsletters e ruído antes do score
- Penalização de remetentes automatizados conhecidos
- Detecção de remetente humano nomeado (formato "Nome `<email>`")
- `action_items` ordenados por relevância no briefing
- Summary textual com breakdown por tipo de email

---

### News / RSS

**Estado inicial:** Listagem bruta de artigos RSS com 4 categorias rudimentares (economia, tecnologia, negocios, geral) derivadas de keyword matching simples no `rss_client.py`. O briefing exibia os 3 primeiros itens da ordem de fetch — completamente arbitrários, sem filtro, sem prioridade, sem deduplicação.

**Evolução em 3 fases:**

**V1 — Classificação Básica**

Criação de `app/integrations/news_classifier.py` como classificador centralizado. Introdução de 8 categorias funcionais (`macro`, `mercado`, `empresas`, `tecnologia`, `politica`, `internacional`, `setorial`, `ruido`) e 7 flags operacionais por artigo. Filtragem de ruído: artigos classificados como `ruido` excluídos dos `items` mas mantidos em `by_category` para auditoria. Fallback por exceção individual. Delegação de classificação para fora do `rss_client.py`.

**V2 — Score, Priorização, Deduplicação e Ordenação**

Modelo de score determinístico com pesos por flag e bônus por categoria. Priority derivada de threshold: `high` (≥ 6), `medium` (≥ 3), `low` (< 3). `score_reasons` auditável. Deduplicação por título normalizado — mantém o item de maior score por grupo. Ordenação única final: `score DESC → published DESC`. Os 3 artigos no topo do briefing passaram a refletir relevância real, não ordem de fetch.

**V3 — Refinamento, Estabilidade e Preparação para V4**

Refinamento de `has_numbers`: de qualquer dígito para número adjacente a marcador econômico (`%`, `R$`, `bi`, `bps`, `bilhões`…). Parsing de datas robusto com cascata ISO 8601 → RFC 2822 → `datetime.min`. Deduplicação limpa: sem penalidade de score no item perdedor. Summary enriquecido com contagem de itens `high`. Remoção de `"desconto"` do set `_NOISE` (ajuste pós-audit: termo genérico que filtrava artigos legítimos de finanças). Inserção de 5 pontos `TODO: [V4]` como marcadores de extensão futura.

**Capacidades atuais:**

- Classificação de artigos em 8 categorias funcionais
- 7 flags operacionais por artigo (impacto em mercado, economia, política, sinal forte, números, duplicata, ruído)
- Score determinístico e auditável com `score_reasons`
- Filtragem de ruído antes do score
- Deduplicação por título normalizado entre feeds
- Ordenação por relevância (score + recência)
- Summary com contagem de itens de alta prioridade
- Fallback robusto em todos os pontos de falha

---

## 3. Estado Atual

| Componente | Status | Pronto para uso real |
|---|---|---|
| RSS Client (fetch) | Estável | Sim |
| News Classifier | Estável (V3) | Sim |
| News Service | Estável (V3) | Sim |
| Email Classifier | Estável (V2) | Sim |
| Inbox Service | Estável (V2) | Sim |
| Briefing Service | Estável | Sim |

O sistema está funcional e foi submetido a audit técnico pré-produção em Abril 2026. O único ajuste blocker identificado (`"desconto"` em `_NOISE`) foi aplicado imediatamente.

**Uso real recomendado:** controlado, com monitoramento ativo nos primeiros dias para validar calibração de score e proporção de itens `high/alta`.

---

## 4. Decisões Arquiteturais Globais

**Determinístico (sem IA):** Decisão deliberada para Fase 1. Comportamento previsível, depurável, sem infraestrutura adicional. Pontos de extensão para IA estão identificados no código (`TODO: [V4]`) mas não implementados.

**Modular por domínio:** Cada módulo (`inbox`, `briefing`, `calendar`) opera de forma independente. O `BriefingService` consolida os dados, mas não conhece as regras internas de nenhum módulo.

**Classificadores isolados em `app/integrations/`:** O `email_classifier.py` e o `news_classifier.py` têm responsabilidade única: classificar um item individual. Não fazem I/O, não mantêm estado, não conhecem listas.

**Sem dependências externas além da stack definida:** `re`, `datetime`, `email.utils` são stdlib. `feedparser` já existia. Nenhum pacote novo foi adicionado nos módulos de classificação.

**Contratos preservados:** Nenhuma interface pública foi quebrada durante a evolução. Campos adicionais são sempre aditivos. O `BriefingService` continua funcionando sem modificação.

**Fallback explícito em todos os pontos de falha:** Falha individual em um artigo ou email nunca aborta o pipeline. O fallback é um dado válido e auditável, não um estado de erro silencioso.

---

## 5. Próximas Etapas

**Imediato — Uso real controlado:**
- Observar proporção de itens `high`/`alta` nos primeiros dias
- Verificar `by_category["ruido"]` para detectar falsos positivos de filtragem
- Validar que os 3 artigos do topo do briefing são semanticamente relevantes

**Curto prazo — Calibração (V3.1):**
- Ajuste fino de pesos e thresholds com base em dados reais de uso
- Possível refinamento de termos em `_NOISE` com base em falsos positivos observados
- Avaliação da proporção `alta` no email (risco de inflação por `"?"` em `_RESPONSE_SIGNALS`)

**Médio prazo — V4:**
- Sumarização de top artigos por LLM (substitui a string de summary)
- Agrupamento temático de artigos por similaridade semântica
- Score de credibilidade por fonte RSS
- Detecção de tópicos tendência entre artigos deduplicados
- Embedding similarity para artigos ambíguos (sem keyword match)

**Estrutural (sem prazo definido):**
- Extração do módulo de notícias para `app/modules/news/` quando o caso de uso de notícias independentes for necessário
- Padronização de labels de prioridade entre email (`alta/media/baixa`) e news (`high/medium/low`)
