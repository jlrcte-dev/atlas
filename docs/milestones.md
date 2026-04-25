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

**V4 — Baseline Determinístico Avançado (Filtros + SimHash)**

Fase de consolidação do motor determinístico antes de qualquer integração com IA.

*Otimização do matching:* substituição de todas as iterações `any(t in text for t in frozenset)` por regex compilados com alternação única (`re.compile`) em `news_classifier.py`. 17 padrões compilados no carregamento do módulo, custo por chamada reduzido de O(n×m) para O(m). Termos ordenados por comprimento decrescente para precedência de frases sobre substrings.

*Normalização centralizada:* criação de `_normalize_text()` em `news_classifier.py` como função utilitária compartilhada. Eliminação da duplicação com `_normalize_title()` em `news_service.py`. Reutilização explícita do texto normalizado entre camadas do pipeline (scope gate → classificação) para evitar recomputação.

*Scope gate híbrido (Modo 3 — portfolio\_macro\_geo):* criação de `app/integrations/tracked_scope.py`. Gate determinístico com três grupos: Grupo A (ativos monitorados: Petrobras, Vale, Ambev, Itaúsa, Ibovespa), Grupo B (macro/política econômica: Selic, Copom, Banco Central, câmbio, dólar, minério de ferro…), Grupo C (geopolítico/social com impacto material: guerra, sanções, conflito internacional, bloqueio logístico, choque de oferta…). Itens descartados no gate não chegam a `classify_news` — elimina custo de classificação sobre notícias fora do escopo. Função pública: `evaluate_scope(normalized_text) -> (bool, str | None)`.

*Near-duplicate gate por SimHash v1:* ativação do módulo `app/integrations/simhash_utils.py` (criado na fase anterior, não integrado até agora). Threshold de 10 bits (conservador). Fingerprint 64-bit via bag-of-words (hashlib.md5). Reutilização de `_normalized_text` já presente no item. Estratégia first-seen (heurística). O(n²) — aceitável para volume atual. Não substitui o dedup exato; opera após ele como segunda barreira.

*Isolamento de campos internos:* itens carregam campos `_`-prefixados durante o pipeline (`_normalized_text`, `_scope_gate_reason_internal`, `_simhash`, `_internal_score`, etc.). Todos removidos pela função `_strip_internal_fields()` antes da serialização — contratos públicos e schemas Pydantic inalterados.

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
| Finance Module | Estável (v1.1) | Sim |

O sistema está funcional e foi submetido a audit técnico pré-produção em Abril 2026. O único ajuste blocker identificado (`"desconto"` em `_NOISE`) foi aplicado imediatamente.

**Uso real recomendado:** controlado, com monitoramento ativo nos primeiros dias para validar calibração de score e proporção de itens `high/alta`.

---

### Finance

**Estado inicial:** módulo inexistente. Gerenciamento financeiro pessoal feito inteiramente via planilha externa, sem persistência no Atlas.

**v1.1 — Primeira versão funcional:**

Módulo independente construído sobre SQLite + FastAPI, sem integração com os módulos existentes (inbox, calendar, news). Objetivo: reproduzir a lógica de uma planilha de gerenciamento financeiro pessoal de forma simples, confiável e com precisão numérica garantida.

**Entidades implementadas:**

- `Account` — contas usadas para conferência manual de saldo (XP, Itaú, Nubank etc.)
- `MonthlyClosing` — saldo inicial do mês; unicidade por `month_ref` garantida em nível de banco
- `FinancialEntry` — lançamentos de receita/despesa com status (`settled`/`pending`) e tipo (`income`/`expense`)
- `AccountBalanceSnapshot` — fotografia manual do saldo de cada conta por mês; unicidade por `(account_id, month_ref)`

**Resumo mensal consolidado (`GET /finance/monthly-summary?month=YYYY-MM`):**

Calcula automaticamente: `expenses_paid`, `expenses_pending`, `income_received`, `income_pending`, `current_balance`, `projected_final_balance`, `conference_total`, `conference_difference`. Requer fechamento mensal cadastrado para o mês solicitado; falha explicitamente caso ausente.

**Decisões técnicas:**

- `NUMERIC(14,2)` + `Decimal` (Python) em todos os valores financeiros — nenhum `float`
- `Decimal(str(value))` no service antes de aritmética — normalização defensiva contra variações do driver SQLite
- `IntegrityError` capturado nos repositories com `rollback()` explícito → exceções Finance tipadas
- `StaticPool` no `conftest.py` — necessário para SQLite in-memory com TestClient ASGI
- Router separado (`finance_routes.py`), registrado em `main.py` com 2 linhas
- `updated_at` setado explicitamente nos `update()` dos repositories

**Cobertura de testes:** 49 testes (service, validação, cálculo, HTTP). Suite completa: 211/211. Zero regressão.

**Capacidades atuais:**

- Registro e listagem de contas de conferência
- Fechamento mensal com saldo inicial e unicidade garantida
- CRUD completo de lançamentos financeiros
- Registro manual de snapshots de saldo por conta e mês
- Resumo financeiro consolidado com conferência
- 5 exceções Finance com códigos estruturados, capturadas pelo handler global (HTTP 400)
- Validação de `month_ref` via regex em duas camadas (schema + service)

---

### Memory Module v1 (Fase 2A · Etapa 1)

**Estado inicial:** o sistema não possuía nenhuma camada de memória. Decisões de classificação (email, news) eram efêmeras: o resultado era servido ao usuário e descartado. Nenhum registro de "o sistema decidiu X sobre o item Y às 10:32".

**Implementação:**

Criação do módulo `app/modules/memory/` como **observer passivo fail-safe** sobre os módulos existentes. Ele captura snapshots de decisão sem alterar fluxo, contratos ou comportamento dos serviços observados.

**Tabela `memory_events`:**

| Campo | Tipo | Notas |
|---|---|---|
| `id` | INTEGER PK | |
| `created_at` | DateTime UTC | indexado |
| `updated_at` | DateTime UTC | atualizado em `update` |
| `event_type` | String(100) | indexado, livre (não enum) |
| `source` | String(100) | indexado, livre |
| `reference_id` | String(255) | nullable, indexado |
| `payload` | Text (JSON) | snapshot completo da decisão |
| `score` | Float | score do classificador no momento |
| `feedback` | String(50) | preenchido pelo Telegram Feedback Loop |

Unicidade: `UniqueConstraint(event_type, reference_id)` — idempotência ao nível de schema.

**Princípios arquiteturais:**

- **Observer passivo:** `_log_email_classifications` e `_log_ranked_news` são invocados após classificação/ranking, em sessões `SessionLocal` próprias (out-of-band). Nenhuma falha de logging propaga ao fluxo principal.
- **Fail-safe tripla:** try/except em `MemoryService.log_event`, em cada helper de logging e a sessão de DB própria isola transações.
- **Idempotência:** `log_event` faz `get_by_type_and_ref` antes de inserir; se existe, atualiza payload + score. Garante reprocessamento seguro do mesmo email/news.
- **Payload como snapshot:** o payload preserva o estado completo da decisão no momento (categoria, prioridade, tags, razões, ID/link original) — não é dado livre. É o registro auditável que justifica o score.
- **`reference_id` normalizado:** via `to_callback_ref(raw, max_len=32)` — se ≤ 32 chars, mantém o ID original (Gmail message IDs); se for maior (URLs), aplica `md5(raw)[:32]`. A mesma função é usada no logging e no botão do Telegram, garantindo lookup direto sem nova tabela ou cache externo.

**Integrações cirúrgicas:**

- `_log_email_classifications` invocado dentro de `InboxService.summarize_emails()` após `_classify_all`. Salva: `event_type=email_classified`, `source=email`, payload com `email_id` original, `category`, `priority`, `tags`, `reason`.
- `_log_ranked_news` invocado dentro de `NewsService.summarize_news()` após curação e diversificação, antes do strip de campos internos. Salva: `event_type=news_ranked`, `source=news`, payload com `link` original, `title`, `category`, `reason`.

**Cobertura de testes:** 22 testes em `tests/test_memory_module.py` — criação, idempotência, fail-safe, `add_feedback`, listagem com filtros, falha do repository não quebrar fluxo Inbox.

**Capacidades atuais:**

- Registro automático de toda decisão de classificação de email
- Registro automático de toda decisão de ranking de news
- Idempotência por `(event_type, reference_id)` — reprocessamento seguro
- Fail-safe completo: falha no Memory **nunca** derruba Inbox/News/Briefing
- Base preparada para feedback loop, score adaptativo e context engine

---

### Telegram Feedback Loop v1 (Fase 2A · Etapa 2)

**Estado inicial:** os eventos do Memory Module v1 eram registrados mas o usuário não tinha como avaliá-los. O ciclo de aprendizado estava aberto.

**Implementação:**

Camada incremental sobre o Memory Module e o Telegram Bot que fecha o primeiro ciclo de feedback ativo:

```text
item exibido → botão pressionado → callback fb:<src>:<ref>:<sig>
   → parse → MemoryService.add_feedback → memory_events.feedback
```

**Fluxo:**

1. Após `/inbox` ou `/news` no Telegram, o webhook envia mensagens individuais por item (top-5 inbox e top-5 news), cada uma com 3 botões de feedback.
2. Botões disponíveis: 👍 **Relevante** (`positive`), 👎 **Irrelevante** (`negative`), ⭐ **Prioridade** (`important`).
3. `callback_data` segue o formato `fb:<src>:<ref>:<sig>`:
   - `src`: `e` (email) ou `n` (news) — limita 1 char.
   - `ref`: `to_callback_ref(reference_id)` — mesmo hash usado no logging, ≤ 32 chars.
   - `sig`: `pos`, `neg` ou `imp` — limita 3 chars.
   - Total: ≤ 41 bytes, **bem dentro do limite de 64 bytes do Telegram**.
4. O webhook intercepta callbacks com prefixo `fb:` ANTES do answer genérico, permitindo `answerCallbackQuery` com texto específico ("Feedback registrado." ou "Não consegui salvar agora, mas registrei sua intenção.").
5. `MemoryService.add_feedback(reference_id, feedback, source=..., event_type=...)` faz lookup pelo índice unique `(event_type, reference_id)` e atualiza apenas o campo `feedback` — não cria novo evento.

**Hash determinístico para IDs longos:**

`to_callback_ref(raw, max_len=32)` é a chave da consistência ponta-a-ponta:

- IDs curtos (Gmail message IDs ≤ 32 chars) preservados como-são — `reference_id` continua legível no DB.
- IDs longos (URLs RSS) viram hash MD5 truncado de 32 chars — colisão astronomicamente improvável para o volume diário do sistema.
- A **mesma função** roda no logging e no botão; lookup pelo hash é direto, sem tabela auxiliar nem cache externo.

**Proteção contra falhas (3 níveis):**

1. **Parser estrito:** `_parse_feedback_callback` rejeita qualquer desvio do contrato (prefixo errado, número errado de partes, src/sig fora do mapa, ref vazio, tipo errado). Defensivo contra payload forjado.
2. **MemoryService fail-safe:** `add_feedback` retorna `bool` — `False` em "evento não encontrado" ou "erro interno". Nunca propaga exceção.
3. **Per-item resilience nos helpers de envio:** após audit, o `try/except` foi movido para dentro do `for` em `send_inbox_items_with_feedback` e `send_news_items_with_feedback`. Falha em um item é logada (warning) e os itens seguintes continuam sendo enviados.

**Integração com `add_feedback` retrocompatível:**

A assinatura foi estendida com kwargs opcionais `source` e `event_type` para desambiguar quando o mesmo `reference_id` aparece em múltiplos `event_type`. Quando `event_type` é fornecido, usa o índice unique direto. Chamadas antigas com apenas `(reference_id, feedback)` continuam funcionando.

**Cobertura de testes:** 36 testes em `tests/test_telegram_feedback.py`:

- Parser de callback (válido + 9 cenários inválidos, type defensivo).
- Limite de 64 bytes do `callback_data` validado com input de 200 chars.
- Persistência de cada sinal (positive/negative/important) em email e news.
- Desambiguação por `event_type` (mesmo `reference_id` em event_types diferentes).
- Fail-safe: parser inválido, MemoryService raise, answer_callback raise, callback_query_id vazio.
- Helpers de envio: skip de itens sem ID, callback dentro do limite, top5 vazio, falha interna.
- **E2E hash invariant** (correção pós-audit): pipeline completo `summarize_emails`/`_log_ranked_news` → memory → button → parse → `add_feedback` → persistência. Prova que o hash salvo no DB é idêntico ao hash que sai pelo callback.
- **Per-item resilience** (correção pós-audit): item 0 raise → itens 1..N continuam.
- **Webhook regression real** via `TestClient`: `/finance` e `fin:menu` não disparam helpers de feedback; `fb:e:<ref>:pos` é roteado corretamente.
- Regressão de intent classifier para `/finance`, `/expense`, `/income`, `/balance`, `/inbox`, `/news`, `/briefing`.

**Capacidades atuais:**

- Botões de feedback automaticamente exibidos por item após `/inbox` e `/news` no Telegram
- Persistência confiável do feedback em `memory_events.feedback`
- Hash determinístico ponta-a-ponta — sem colisão prática, sem nova tabela, sem cache
- Fail-safe completo — webhook nunca quebra por feedback
- Suite de regressão protegida contra futuras alterações que rompam a invariante hash

**Limitações conhecidas (v1):**

- Briefing consolidado (`format_briefing_blocks`, `/admin/trigger-briefing`) não exibe botões de feedback — limitação aceita; eventos seguem sendo registrados, mas não há UX de feedback nesse fluxo.
- Itens sem `reference_id` válido (link/ID ausente) são silenciosamente pulados.
- Sem indicação visual quando o usuário já avaliou um item — clicar duas vezes apenas atualiza o registro.
- `add_feedback` retorna `False` indistintamente para "evento não encontrado" e "erro interno" — mensagem soft-fail é a mesma.

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
